"""
Unit tests for the one scope rule (ADR-0024).

All offline: pure string and regex work, no network and no Qt.
Run with: pytest tests/test_scope.py -v
"""

from app.core import scope


def test_normalise_strips_at_and_case() -> None:
    """A target may be typed with or without a leading @."""
    assert scope.normalise("@BHP.com ") == "bhp.com"
    assert scope.normalise("Nunoa.CL") == "nunoa.cl"


def test_normalise_reads_nothing_as_empty() -> None:
    """'' is a real answer meaning .cl scope, not a missing value."""
    assert scope.normalise(None) == ""
    assert scope.normalise("") == ""
    assert scope.normalise("   ") == ""


def test_covers_accepts_the_domain_and_its_subdomains() -> None:
    assert scope.covers("bhp.com", "bhp.com")
    assert scope.covers("careers.bhp.com", "bhp.com")


def test_covers_rejects_a_lookalike() -> None:
    """A bare endswith would put a stranger's address in a mailable file."""
    assert not scope.covers("notbhp.com", "bhp.com")
    assert not scope.covers("notnunoa.cl", "nunoa.cl")
    assert not scope.covers("bhp.com.mx", "bhp.com")


def test_in_scope_without_a_target_is_cl_only() -> None:
    """Every scan that works today keeps working the same way."""
    assert scope.in_scope("contacto@nunoa.cl")
    assert not scope.in_scope("sarah@bhp.com")


def test_in_scope_with_a_target_follows_the_target() -> None:
    """The whole point: a named domain is in scope whatever its TLD."""
    assert scope.in_scope("sarah@bhp.com", "bhp.com")
    assert scope.in_scope("sarah@careers.bhp.com", "bhp.com")
    assert not scope.in_scope("contacto@nunoa.cl", "bhp.com")


def test_in_scope_rejects_a_non_address() -> None:
    assert not scope.in_scope("notanemail", "bhp.com")
    assert not scope.in_scope("@bhp.com", "bhp.com")


def test_host_in_scope_keeps_cl_when_a_target_is_named() -> None:
    """
    A Chilean site linked from the target is still worth crawling.

    Narrowing to the target alone would make a .com scan blind to exactly
    the Chilean pages it is looking for.
    """
    assert scope.host_in_scope("https://www.bhp.com/careers", "bhp.com")
    assert scope.host_in_scope("https://nunoa.cl/contacto", "bhp.com")
    assert not scope.host_in_scope("https://example.org/x", "bhp.com")


def test_host_in_scope_without_a_target_is_cl_only() -> None:
    assert scope.host_in_scope("https://nunoa.cl/contacto")
    assert not scope.host_in_scope("https://www.bhp.com/careers")
    assert not scope.host_in_scope("not a url")


def test_email_re_matches_the_target_and_cl_together() -> None:
    """
    .cl stays matched with a target set.

    pipeline needs to see the .cl addresses it is about to discard so it
    can report them rather than folding them into a zero.
    """
    text = "sarah@bhp.com, contacto@nunoa.cl, otro@ajeno.org"

    assert sorted(
        m.group() for m in scope.email_re("bhp.com").finditer(text)
    ) == ["contacto@nunoa.cl", "sarah@bhp.com"]


def test_email_re_without_a_target_matches_cl_only() -> None:
    text = "sarah@bhp.com contacto@nunoa.cl"

    assert [m.group() for m in scope.email_re().finditer(text)] == [
        "contacto@nunoa.cl"
    ]


def test_obfuscated_re_covers_the_target_too() -> None:
    """De-obfuscation was .cl-only for the same reason extraction was."""
    text = "sarah [at] bhp.com"

    assert scope.obfuscated_re("bhp.com").search(text)
    assert not scope.obfuscated_re().search(text)


def test_url_re_covers_the_target_too() -> None:
    """The DuckDuckGo result regex captured no URL for a .com target."""
    html = 'href="https://www.bhp.com/contact" x="https://nunoa.cl/a"'

    assert sorted(
        m.group() for m in scope.url_re("bhp.com").finditer(html)
    ) == ["https://nunoa.cl/a", "https://www.bhp.com/contact"]
    assert [m.group() for m in scope.url_re().finditer(html)] == [
        "https://nunoa.cl/a"
    ]


def test_a_target_with_regex_metacharacters_is_escaped() -> None:
    """A dot in a domain must not match any character."""
    assert not scope.in_scope("x@bhpXcom", "bhp.com")
    assert not scope.email_re("bhp.com").search("x@bhpXcom")
