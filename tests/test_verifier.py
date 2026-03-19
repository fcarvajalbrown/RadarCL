"""
Unit tests for the email verifier.

Run with: pytest tests/test_verifier.py -v

Note: SMTP tests require a live internet connection.
      Run with: pytest -m "not smtp" to skip them offline.
"""

import pytest
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


def test_no_smtp_returns_unknown() -> None:
    """With smtp_enabled=False and valid MX domain, status should be UNKNOWN."""
    result = verify("user@bcn.cl", smtp_enabled=False)
    assert result.syntax_ok is True
    assert result.mx_ok is True
    assert result.status == VStatus.UNKNOWN
    assert result.smtp_ok is None


def test_invalid_mx_domain() -> None:
    """Domain with no MX records should return INVALID."""
    result = verify("user@thisdoesnotexist123456.cl", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.mx_ok is False


def test_error_message_populated_on_failure() -> None:
    """Failed verification should populate the error field."""
    result = verify("user@thisdoesnotexist123456.cl", smtp_enabled=False)
    assert result.error != ""


@pytest.mark.smtp
def test_smtp_valid_known_domain() -> None:
    """
    Known live .cl domain should return VALID or UNKNOWN via SMTP.
    UNKNOWN is acceptable — many servers block SMTP probing.
    """
    result = verify("contacto@bcn.cl", smtp_enabled=True)
    assert result.status in (VStatus.VALID, VStatus.UNKNOWN)
    assert result.syntax_ok is True
    assert result.mx_ok is True