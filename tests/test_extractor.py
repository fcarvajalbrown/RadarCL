"""
Unit tests for the email extractor.

Run with: pytest tests/test_extractor.py -v
"""

import pytest

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

# ── Hidden addresses: spam traps, not contacts

# Each of these is a documented honeypot placement. An address planted this
# way has never belonged to a person; it is there so that whoever mails it
# identifies themselves as a harvester, and one delivery is grounds for a
# Spamhaus listing that costs the sender every other address they hold.
HIDING_TECHNIQUES = [
    ('display:none', '<div style="display:none">{a}</div>'),
    ('visibility:hidden', '<span style="visibility:hidden">{a}</span>'),
    ('opacity:0', '<div style="opacity:0">{a}</div>'),
    ('white on white', '<div style="color:#fff;background:#fff">{a}</div>'),
    ('font-size:0 mailto', '<a href="mailto:{a}" style="font-size:0">.</a>'),
    ('off-screen indent', '<div style="text-indent:-9999px">{a}</div>'),
    ('aria-hidden', '<div aria-hidden="true">{a}</div>'),
    ('hidden attribute', '<div hidden>{a}</div>'),
    ('hidden mailto in hidden div',
     '<div style="display:none"><a href="mailto:{a}">x</a></div>'),
]


@pytest.mark.parametrize(
    'label,markup', HIDING_TECHNIQUES, ids=[t[0] for t in HIDING_TECHNIQUES]
)
def test_hidden_addresses_are_marked(label: str, markup: str) -> None:
    """Every documented hiding technique must come back flagged."""
    html = f'<p>real@nunoa.cl</p>{markup.format(a="trap@nunoa.cl")}'
    results = {r['email']: r['hidden'] for r in extract_emails(html, 'u')}

    assert results['trap@nunoa.cl'] is True, f'{label} was not detected'
    assert results['real@nunoa.cl'] is False


def test_visible_addresses_are_not_marked() -> None:
    """An ordinary contact block carries no flag."""
    html = '''
        <p>Contacto: <a href="mailto:info@nunoa.cl">escríbenos</a></p>
        <p>o bien alcaldia@nunoa.cl</p>
        <p>prensa [at] nunoa.cl</p>
    '''
    results = extract_emails(html, 'u')

    assert len(results) == 3
    assert not any(r['hidden'] for r in results)


def test_address_seen_visibly_is_not_a_trap() -> None:
    """
    An address that appears in both places is visible, not hidden.

    Sites repeat a contact address inside collapsed menus and print-only
    blocks all the time. What marks a trap is that a reader could *never*
    have seen it, so one visible occurrence settles the question.
    """
    html = '''
        <p>contacto@nunoa.cl</p>
        <div style="display:none">contacto@nunoa.cl</div>
    '''
    results = extract_emails(html, 'u')

    assert len(results) == 1
    assert results[0]['hidden'] is False


def test_hidden_addresses_are_still_returned() -> None:
    """
    They are flagged, never silently dropped.

    ADR-0014 established that provenance annotates rather than filters, and
    the run record is where a user finds out a page carried a trap. Only
    the CSV excludes them, which `exporter` does.
    """
    html = '<div style="display:none">trap@nunoa.cl</div>'
    results = extract_emails(html, 'u')

    assert [r['email'] for r in results] == ['trap@nunoa.cl']
    assert results[0]['hidden'] is True
