"""
Multi-stage email verifier.

Stages (run in order):
  1. Syntax  — regex format check
  2. MX      — DNS MX record lookup
  3. SMTP    — handshake without sending email
  4. API     — optional third-party (placeholder)
"""

import re
import smtplib
import socket
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import dns.resolver


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
    api_status: Optional[str] = None
    error: str = ""


_SYNTAX_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.cl$',
    re.IGNORECASE
)


def verify(
    email: str,
    smtp_enabled: bool = True,
    api_key: str | None = None,
) -> VerificationResult:
    """
    Run all verification stages for a single email address.

    Parameters
    ----------
    email : str
        The address to verify.
    smtp_enabled : bool
        If False, skip the SMTP handshake stage.
    api_key : str | None
        Enables Stage 4 if provided.

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
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_host = str(
            sorted(mx_records, key=lambda r: r.preference)[0].exchange
        ).rstrip('.')
        result.mx_ok = True
    except Exception as exc:
        result.status = VStatus.INVALID
        result.error = f"No MX record: {exc}"
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
            result.status = VStatus.VALID if result.smtp_ok else VStatus.INVALID
            if not result.smtp_ok:
                result.error = f"SMTP RCPT code {code}"
    except (smtplib.SMTPException, socket.error, OSError) as exc:
        result.smtp_ok = None
        result.status = VStatus.UNKNOWN
        result.error = f"SMTP error: {exc}"

    # Stage 4: API (placeholder)
    if api_key and result.status == VStatus.UNKNOWN:
        result.api_status = "not_implemented"

    return result