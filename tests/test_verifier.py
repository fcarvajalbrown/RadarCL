"""
Unit tests for the email verifier.

Run with: pytest tests/test_verifier.py -v

Note: tests marked `smtp` require a live internet connection — either a
      DNS MX lookup, an SMTP handshake, or both.
      Run with: pytest -m "not smtp" to skip them offline.
"""

import pytest
from app.core import verifier
from app.core.verifier import verify, VStatus


def test_invalid_syntax_missing_at() -> None:
    """Address with no @ should fail syntax stage."""
    result = verify("notanemail", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.syntax_ok is False


def test_invalid_syntax_wrong_tld() -> None:
    """Non-.cl address should fail syntax stage."""
    result = verify("user@company.com", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.syntax_ok is False


def test_invalid_syntax_no_domain() -> None:
    """Address with no domain should fail syntax stage."""
    result = verify("user@.cl", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.syntax_ok is False


def test_valid_syntax_passes() -> None:
    """Well-formed .cl address should pass syntax stage."""
    result = verify("user@example.cl", smtp_enabled=False)
    assert result.syntax_ok is True


@pytest.mark.smtp
def test_no_smtp_returns_unknown() -> None:
    """With smtp_enabled=False and valid MX domain, status should be UNKNOWN."""
    result = verify("user@bcn.cl", smtp_enabled=False)
    assert result.syntax_ok is True
    assert result.mx_ok is True
    assert result.status == VStatus.UNKNOWN
    assert result.smtp_ok is None


@pytest.mark.smtp
def test_invalid_mx_domain() -> None:
    """Domain with no MX records should return INVALID."""
    result = verify("user@thisdoesnotexist123456.cl", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.mx_ok is False


@pytest.mark.smtp
def test_error_message_populated_on_failure() -> None:
    """Failed verification should populate the error field."""
    result = verify("user@thisdoesnotexist123456.cl", smtp_enabled=False)
    assert result.error != ""


def test_mx_resolver_failure_is_unknown(monkeypatch) -> None:
    """
    A resolver that cannot answer is no information, not a verdict.

    This is the bug that reported 16 real @nunoa.cl addresses as INVALID:
    dnspython timed out against the configured nameservers, and the MX
    stage treated that identically to a nonexistent domain. See ADR-0009.
    """
    def _unavailable(domain):
        raise verifier.MXUnavailable("LifetimeTimeout: resolution expired")

    monkeypatch.setattr(verifier, "resolve_mx", _unavailable)
    result = verify("gbenavides@nunoa.cl", smtp_enabled=True)

    assert result.status == VStatus.UNKNOWN
    assert result.mx_ok is False
    assert "LifetimeTimeout" in result.error


def test_nonexistent_domain_is_still_invalid(monkeypatch) -> None:
    """A domain that definitively does not exist stays INVALID."""
    def _missing(domain):
        raise verifier.DomainNotFound(f"{domain} does not exist")

    monkeypatch.setattr(verifier, "resolve_mx", _missing)
    result = verify("user@thisdoesnotexist123456.cl", smtp_enabled=True)

    assert result.status == VStatus.INVALID
    assert result.mx_ok is False


def test_resolved_mx_reaches_the_smtp_stage(monkeypatch) -> None:
    """A successful lookup marks mx_ok and proceeds to SMTP."""
    monkeypatch.setattr(
        verifier, "resolve_mx", lambda domain: "aspmx.l.google.com"
    )
    monkeypatch.setattr(
        verifier.smtplib, "SMTP", type("_P", (_FakeSMTP,), {"rcpt_code": 250})
    )
    result = verify("gbenavides@nunoa.cl", smtp_enabled=True)

    assert result.mx_ok is True
    assert result.status == VStatus.VALID


class _FakeSMTP:
    """Stand-in for smtplib.SMTP returning a canned RCPT reply code."""

    rcpt_code = 250

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def connect(self, host, port):
        return (220, b"ready")

    def helo(self, name=""):
        return (250, b"ok")

    def mail(self, sender):
        return (250, b"ok")

    def rcpt(self, recipient):
        return (self.rcpt_code, b"canned reply")


@pytest.fixture
def smtp_code(monkeypatch):
    """Force verify()'s SMTP stage to return a given RCPT reply code."""
    def _apply(code: int) -> None:
        monkeypatch.setattr(
            verifier, "resolve_mx", lambda domain: "mx.example.cl"
        )
        monkeypatch.setattr(
            verifier.smtplib,
            "SMTP",
            type("_Patched", (_FakeSMTP,), {"rcpt_code": code}),
        )
    return _apply


def test_smtp_250_is_valid(smtp_code) -> None:
    """A 250 acceptance is the only VALID outcome."""
    smtp_code(250)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.VALID
    assert result.smtp_ok is True


def test_smtp_550_is_invalid(smtp_code) -> None:
    """550 is a permanent failure: mailbox does not exist."""
    smtp_code(550)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.INVALID
    assert result.smtp_ok is False
    assert "550" in result.error


def test_smtp_450_greylisting_is_unknown(smtp_code) -> None:
    """450 is a transient deferral (greylisting), not a rejection."""
    smtp_code(450)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.UNKNOWN
    assert "450" in result.error


def test_smtp_421_rate_limit_is_unknown(smtp_code) -> None:
    """421 is a transient rate-limit, not a rejection."""
    smtp_code(421)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.UNKNOWN


def test_smtp_252_cannot_verify_is_unknown(smtp_code) -> None:
    """252 means the server states it cannot verify the address."""
    smtp_code(252)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.UNKNOWN


@pytest.mark.smtp
def test_smtp_stage_runs_against_a_live_domain() -> None:
    """
    The pipeline reaches the SMTP stage against a real server and classifies
    the reply. What that reply is, is not this test's business.

    It used to assert that contacto@bcn.cl came back VALID or UNKNOWN, which
    passed until the mailbox was retired and the server began answering 550.
    The verifier was right and the test was wrong: it had outsourced its
    assertion to whether a stranger's mailbox still existed, so a correct
    INVALID read as a regression. What is ours to check is that syntax and MX
    ran, that the handshake completed rather than raising, and that whatever
    came back landed in one of the three buckets ADR-0009 defines.
    """
    result = verify("contacto@bcn.cl", smtp_enabled=True)
    assert result.syntax_ok is True
    assert result.mx_ok is True
    assert result.status in (VStatus.VALID, VStatus.UNKNOWN, VStatus.INVALID)
    # A definitive answer must say which one it was. UNKNOWN is the bucket
    # for "could not tell", so it is the only status allowed to carry no
    # reason (ADR-0004, ADR-0009).
    if result.status is not VStatus.UNKNOWN:
        assert result.error or result.smtp_ok, result