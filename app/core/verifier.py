"""
Multi-stage email verifier.

Stages (run in order):
  1. Syntax  — regex format check
  2. MX      — DNS MX lookup with fallback transports; a nonexistent
               domain is invalid, an unanswerable resolver is unknown
               (ADR-0009)
  3. SMTP    — handshake without sending email; 250 valid,
               5xx invalid, 4xx/252 unknown (ADR-0007)

Three stages, not four. A fourth "optional third-party API" stage existed
as a placeholder until v0.55 and was removed rather than built: no
interface exposed it, nothing read its output, and the commercial APIs it
would have called are 70-85% accurate on catch-all domains, which is the
case this project actually needs solved (ADR-0015).
"""

import re
import smtplib
import socket
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from app.core.dns_lookup import DomainNotFound, MXUnavailable, resolve_mx


class VStatus(Enum):
    """Verification outcome."""
    VALID = auto()
    UNKNOWN = auto()
    INVALID = auto()


@dataclass
class VerificationResult:
    """Full verification report for one email address."""
    email: str
    status: VStatus = VStatus.UNKNOWN
    syntax_ok: bool = False
    mx_ok: bool = False
    smtp_ok: Optional[bool] = None
    error: str = ""


_SYNTAX_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.cl$',
    re.IGNORECASE
)


def verify(
    email: str,
    smtp_enabled: bool = True,
) -> VerificationResult:
    """
    Run all verification stages for a single email address.

    Parameters
    ----------
    email : str
        The address to verify.
    smtp_enabled : bool
        If False, skip the SMTP handshake stage.

    Returns
    -------
    VerificationResult
    """
    result = VerificationResult(email=email)

    # Stage 1: Syntax
    if not _SYNTAX_RE.match(email):
        result.status = VStatus.INVALID
        result.error = "Invalid email format"
        return result
    result.syntax_ok = True

    # Stage 2: MX
    domain = email.split('@')[1]
    try:
        mx_host = resolve_mx(domain)
        result.mx_ok = True
    except DomainNotFound as exc:
        # Definitive: the domain has nowhere to deliver mail.
        result.status = VStatus.INVALID
        result.error = f"No MX record: {exc}"
        return result
    except MXUnavailable as exc:
        # No transport could answer. That says nothing about the address,
        # so it must not be reported as invalid — see ADR-0009.
        result.status = VStatus.UNKNOWN
        result.error = f"MX lookup failed: {exc}"
        return result

    if not smtp_enabled:
        result.status = VStatus.UNKNOWN
        return result

    # Stage 3: SMTP handshake
    try:
        with smtplib.SMTP(timeout=10) as smtp:
            smtp.connect(mx_host, 25)
            smtp.helo('verify.cl')
            smtp.mail('check@verify.cl')
            code, _ = smtp.rcpt(email)
            result.smtp_ok = code == 250
            if result.smtp_ok:
                result.status = VStatus.VALID
            elif 500 <= code < 600:
                # Permanent failure per RFC 5321 — 550 5.1.1 is
                # "Bad destination mailbox address". See ADR-0007.
                result.status = VStatus.INVALID
                result.error = f"SMTP RCPT code {code}"
            else:
                # 4xx is transient by definition (450/451 greylisting,
                # 421 rate-limiting) and 252 means the server says it
                # cannot verify. Absence of information, not rejection.
                result.status = VStatus.UNKNOWN
                result.error = f"SMTP RCPT code {code}"
    except (smtplib.SMTPException, socket.error, OSError) as exc:
        result.smtp_ok = None
        result.status = VStatus.UNKNOWN
        result.error = f"SMTP error: {exc}"

    return result