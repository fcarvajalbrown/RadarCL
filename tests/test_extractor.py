"""
Unit tests for the email extractor.

Run with: pytest tests/test_extractor.py -v
"""

from app.core.extractor import extract_emails


def test_extracts_mailto() -> None:
    """Should extract email from a mailto: link."""
    html = '<a href="mailto:contacto@empresa.cl">Email</a>'
    results = extract_emails(html, "https://empresa.cl")
    assert any(r['email'] == 'contacto@empresa.cl' for r in results)


def test_extracts_plain_text() -> None:
    """Should extract email embedded in plain text."""
    html = '<p>Escríbenos a ventas@ejemplo.cl para más info.</p>'
    results = extract_emails(html, "https://ejemplo.cl")
    assert any(r['email'] == 'ventas@ejemplo.cl' for r in results)


def test_ignores_non_cl() -> None:
    """Should not extract non-.cl email addresses."""
    html = '<p>Contact us at support@company.com</p>'
    results = extract_emails(html, "https://empresa.cl")
    assert all(r['email'].endswith('.cl') for r in results)


def test_deobfuscates_at() -> None:
    """Should normalise obfuscated [at] patterns."""
    html = '<p>info [at] empresa.cl</p>'
    results = extract_emails(html, "https://empresa.cl")
    assert any(r['email'] == 'info@empresa.cl' for r in results)


def test_deobfuscates_parentheses_at() -> None:
    """Should normalise obfuscated (at) patterns."""
    html = '<p>info (at) empresa.cl</p>'
    results = extract_emails(html, "https://empresa.cl")
    assert any(r['email'] == 'info@empresa.cl' for r in results)


def test_normalises_to_lowercase() -> None:
    """Should return all emails in lowercase."""
    html = '<a href="mailto:Felipe.Carvajal@BHP.cl">Email</a>'
    results = extract_emails(html, "https://bhp.cl")
    assert any(r['email'] == 'felipe.carvajal@bhp.cl' for r in results)


def test_deduplicates_same_email() -> None:
    """Should not return duplicate emails from the same page."""
    html = '''
        <a href="mailto:contacto@empresa.cl">Email</a>
        <p>contacto@empresa.cl</p>
    '''
    results = extract_emails(html, "https://empresa.cl")
    emails = [r['email'] for r in results]
    assert emails.count('contacto@empresa.cl') == 1


def test_source_url_attached() -> None:
    """Each result should carry the source URL."""
    html = '<p>info@empresa.cl</p>'
    results = extract_emails(html, "https://empresa.cl/contacto")
    assert all(r['source'] == 'https://empresa.cl/contacto' for r in results)


def test_empty_page_returns_empty() -> None:
    """Empty HTML should return no results."""
    results = extract_emails("", "https://empresa.cl")
    assert results == []