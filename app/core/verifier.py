"""
Multi-stage email verifier.

Stages (run in order):
  1. Syntax  — regex format check
  2. MX      — DNS MX lookup with fallback transports; a nonexistent
               domain is invalid, an unanswerable resolver is unknown
               (ADR-0009)
  3. SMTP    — handshake without sending email. 250 is VALID, unless the
               server accepts every recipient, which is CATCH_ALL
               (ADR-0016). 4xx and 252 are UNKNOWN. A 5xx is INVALID only
               when its RFC 3463 subject says it is about the address;
               policy, routing and protocol failures are facts about the
               sender or the path, so they are UNKNOWN too

Three stages, not four. A fourth "optional third-party API" stage existed
as a placeholder until v0.55 and was removed rather than built: no
interface exposed it, nothing read its output, and the commercial APIs it
would have called are 70-85% accurate on catch-all domains, which is the
case this project actually needs solved (ADR-0015).
"""

import os
import re
import secrets
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
    CATCH_ALL = auto()


# Local parts for the catch-all probe. High entropy on purpose: some
# servers reject addresses matching known abuse patterns while accepting
# everything else, so a guessable probe reports "not catch-all" on a
# server that is one. Two probes rather than one, because servers with
# deferred rejection can accept a single unlucky address (ADR-0016).
_CATCH_ALL_PROBES = 2
_PROBE_LOCAL_BYTES = 10  # 20 hex characters

# RFC 3463 enhanced status code, e.g. `550 5.1.1 ...` or `451 4.7.1 ...`.
_ENHANCED_RE = re.compile(rb'\b([245])\.(\d+)\.(\d+)\b')

# RFC 3463's middle digit is the *subject*: which part of the mail system
# the status is about. Only two subjects speak about the recipient at all.
#
#   1  addressing   the address itself       -> about the mailbox
#   2  mailbox      the mailbox itself       -> about the mailbox
#   3  mail system  their system             -> about them
#   4  network      routing                  -> about the path
#   5  protocol     this conversation        -> about us
#   6  content      the message              -> about the message
#   7  security     policy, authentication   -> about us
#
# A permanent failure with subject 3 through 7 is a permanent fact about
# something other than the address, so it cannot be evidence the address
# is dead. Reading every 5xx as INVALID marked live addresses dead in the
# CSV, which is the error ADR-0009 fixed for DNS, one stage later.
_SUBJECTS_ABOUT_THE_MAILBOX = {1, 2}

# The exception inside subject 2: X.2.2 is "mailbox full". A full mailbox
# is proof the mailbox *exists*, so INVALID is plainly wrong. It is not
# VALID either, since mail to it bounces today, and the CSV is the list
# you send to. It is the textbook UNKNOWN: real, and not deliverable now.
_MAILBOX_FULL = (2, 2)

# Text a server uses when it is deferring rather than refusing. A 4xx is
# already UNKNOWN; this marks the subset worth asking again, since
# greylisting answers differently on a later attempt from the same IP.
_GREYLIST_HINTS = (
    b'greylist', b'grey list', b'graylist', b'try again', b'try later',
    b'temporarily deferred', b'deferred', b'come back',
)


@dataclass
class VerificationResult:
    """Full verification report for one email address."""
    email: str
    status: VStatus = VStatus.UNKNOWN
    syntax_ok: bool = False
    mx_ok: bool = False
    smtp_ok: Optional[bool] = None
    greylisted: bool = False
    error: str = ""


_SYNTAX_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)*\.[a-zA-Z]{2,}$',
    re.IGNORECASE
)


def _enhanced(msg: bytes | str | None) -> tuple[int, int] | None:
    """Return (subject, detail) of an RFC 3463 code, or None if absent."""
    if msg is None:
        return None
    raw = msg if isinstance(msg, bytes) else str(msg).encode('utf-8', 'replace')
    match = _ENHANCED_RE.search(raw)
    return (int(match.group(2)), int(match.group(3))) if match else None


def _looks_greylisted(code: int, msg: bytes | str | None) -> bool:
    """
    True if a 4xx reply reads as greylisting rather than plain congestion.

    Greylisting answers differently on a later attempt from the same IP,
    so it is the one transient failure worth asking again. 421 is excluded:
    it means the server is shedding load or rate-limiting, and retrying
    that promptly is how a temporary deferral becomes a block.
    """
    if not (400 <= code < 500) or code == 421:
        return False
    raw = msg if isinstance(msg, bytes) else str(msg or '').encode('utf-8', 'replace')
    low = raw.lower()
    if any(hint in low for hint in _GREYLIST_HINTS):
        return True
    # 450 and 451 are the codes greylisters use; treat them as candidates
    # even when the server explains nothing, since the retry is cheap and
    # the alternative is calling a live address unknown forever.
    return code in (450, 451)


def _helo_name() -> str:
    """
    The name RadarCL announces itself by.

    Until v0.60 this was the literal string `verify.cl`, and the envelope
    sender was `check@verify.cl`. `verify.cl` is a registered domain
    belonging to someone else, so every probe RadarCL had ever sent
    attributed itself to a stranger: any complaint, bounce or blocklisting
    earned by this tool landed on them. Servers that check whether the
    HELO name matches the connecting IP also read it as impersonation.

    The machine's own fully qualified name is what a real mail server
    sends. It may not resolve back to this host, which some servers
    penalise, but it is honest, and being penalised for what you are beats
    passing for someone else.

    `RADARCL_HELO` overrides it. Anyone running this from a host with a
    real domain and a matching PTR record will get better acceptance by
    setting it, and that is the only correct way to improve the odds here:
    the alternative is naming a domain you do not control.
    """
    override = os.environ.get('RADARCL_HELO', '').strip()
    if override:
        return override

    name = socket.getfqdn()
    if not name or '.' not in name or name.startswith('localhost'):
        return 'localhost.localdomain'
    return name


def _open_transaction(smtp: smtplib.SMTP, helo: str) -> None:
    """
    Say hello and open a mail transaction with the null sender.

    `MAIL FROM:<>` is the convention for probes that will never send: it is
    what bounce messages carry and what Postfix's own address verification
    uses, and it guarantees no reply can be generated. A minority of
    servers reject the null sender, so those fall back to `postmaster@`,
    the other documented convention for callback verification.
    """
    smtp.helo(helo)
    code, _msg = smtp.mail('')
    if code >= 400:
        smtp.rset()
        smtp.mail(f'postmaster@{helo}')


def _is_catch_all(smtp: smtplib.SMTP, domain: str) -> bool:
    """
    Ask a mail server whether it accepts addresses that cannot exist.

    Reuses the caller's open connection, so detection costs extra RCPT
    commands rather than an extra session. Every probe must be accepted
    before the domain is called catch-all: one rejection proves the server
    distinguishes real mailboxes from invented ones, which is the whole
    question.

    Returns False on any error, since failing to prove a server accepts
    everything is not evidence that it does.
    """
    for _ in range(_CATCH_ALL_PROBES):
        probe = f"{secrets.token_hex(_PROBE_LOCAL_BYTES)}@{domain}"
        try:
            code, _msg = smtp.rcpt(probe)
        except (smtplib.SMTPException, socket.error, OSError):
            return False
        if code != 250:
            return False
    return True


def verify(
    email: str,
    smtp_enabled: bool = True,
    catch_all_cache: dict[str, bool] | None = None,
) -> VerificationResult:
    """
    Run all verification stages for a single email address.

    Parameters
    ----------
    email : str
        The address to verify.
    smtp_enabled : bool
        If False, skip the SMTP handshake stage.
    catch_all_cache : dict[str, bool] | None
        Domain to catch-all verdict, reused across addresses. Catch-all is
        a property of the mail server, not of the mailbox, so verifying 23
        addresses at one domain should ask its server once. Pass the same
        dict for a whole run; None probes every time, which is correct but
        wasteful and looks like harvesting to the far end.

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
            _open_transaction(smtp, _helo_name())
            code, msg = smtp.rcpt(email)
            result.smtp_ok = code == 250
            if result.smtp_ok:
                # A 250 only means the server accepted the recipient. On a
                # catch-all server it accepts everything, so it is not
                # evidence the mailbox exists (ADR-0016).
                if catch_all_cache is not None and domain in catch_all_cache:
                    catch_all = catch_all_cache[domain]
                else:
                    catch_all = _is_catch_all(smtp, domain)
                    if catch_all_cache is not None:
                        catch_all_cache[domain] = catch_all
                if catch_all:
                    result.status = VStatus.CATCH_ALL
                    result.error = (
                        "Domain accepts all recipients; 250 is not proof "
                        "the mailbox exists"
                    )
                else:
                    result.status = VStatus.VALID
            elif 500 <= code < 600:
                # Permanent failure per RFC 5321 — 550 5.1.1 is
                # "Bad destination mailbox address". See ADR-0007.
                #
                # But not every permanent failure is about the mailbox. A
                # 550 5.7.1 means the server refuses *this sender*, which
                # is a fact about RadarCL, not about the address, and
                # reporting it INVALID marks working addresses dead for
                # everyone who reads the CSV. Same error ADR-0009 fixed
                # for DNS, one stage later.
                enhanced = _enhanced(msg)
                if enhanced == _MAILBOX_FULL:
                    result.status = VStatus.UNKNOWN
                    result.error = (
                        f"SMTP RCPT code {code}: mailbox full, so it exists "
                        f"but will not take mail right now"
                    )
                elif enhanced is None or enhanced[0] in _SUBJECTS_ABOUT_THE_MAILBOX:
                    result.status = VStatus.INVALID
                    result.error = f"SMTP RCPT code {code}"
                else:
                    result.status = VStatus.UNKNOWN
                    result.error = (
                        f"SMTP RCPT code {code}: refused over policy, routing "
                        f"or protocol, which says nothing about this address"
                    )
            else:
                # 4xx is transient by definition (450/451 greylisting,
                # 421 rate-limiting) and 252 means the server says it
                # cannot verify. Absence of information, not rejection.
                result.status = VStatus.UNKNOWN
                result.greylisted = _looks_greylisted(code, msg)
                result.error = f"SMTP RCPT code {code}"
                if result.greylisted:
                    result.error += " (greylisted, worth retrying)"
    except (smtplib.SMTPException, socket.error, OSError) as exc:
        result.smtp_ok = None
        result.status = VStatus.UNKNOWN
        result.error = f"SMTP error: {exc}"

    return result