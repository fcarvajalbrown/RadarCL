"""Tests for the CSV/JSON/HTML exporters."""

import json

import pytest

from app.core.exporter import (
    export,
    export_html,
    export_json,
    export_valid,
    infer_format,
    summarize,
)

RESULTS = [
    {'email': 'ok@nunoa.cl', 'source': 'https://nunoa.cl/contacto',
     'status': 'valid', 'error': ''},
    {'email': 'quizas@nunoa.cl', 'source': 'https://nunoa.cl/equipo',
     'status': 'unknown', 'error': 'SMTP RCPT code 450'},
    {'email': 'no@nunoa.cl', 'source': 'https://nunoa.cl/equipo',
     'status': 'invalid', 'error': 'SMTP RCPT code 550'},
]


def test_csv_still_exports_only_valid(tmp_path):
    """CSV keeps its historical meaning: the mailable list, VALID only."""
    path = export_valid(RESULTS, tmp_path / 'out.csv')
    body = path.read_text(encoding='utf-8')

    assert 'ok@nunoa.cl' in body
    assert 'quizas@nunoa.cl' not in body
    assert 'no@nunoa.cl' not in body


def test_json_carries_every_status(tmp_path):
    """JSON is a record of the run, so nothing is filtered out."""
    path = export_json(RESULTS, tmp_path / 'out.json')
    payload = json.loads(path.read_text(encoding='utf-8'))

    emails = [row['email'] for row in payload['results']]
    assert emails == ['ok@nunoa.cl', 'quizas@nunoa.cl', 'no@nunoa.cl']


def test_json_records_keep_the_failure_reason(tmp_path):
    """The error field is the reason an UNKNOWN is worth retrying."""
    path = export_json(RESULTS, tmp_path / 'out.json')
    payload = json.loads(path.read_text(encoding='utf-8'))

    unknown = next(r for r in payload['results'] if r['status'] == 'unknown')
    assert unknown['error'] == 'SMTP RCPT code 450'


def test_json_includes_summary_counts(tmp_path):
    """A consumer should not have to re-tally the rows."""
    path = export_json(RESULTS, tmp_path / 'out.json')
    payload = json.loads(path.read_text(encoding='utf-8'))

    assert payload['summary'] == {
        'total': 3, 'valid': 1, 'unknown': 1, 'invalid': 1
    }


def test_summarize_counts_unexpected_statuses_too():
    """An unknown status value must not raise, nor be silently dropped."""
    counts = summarize([{'email': 'a@b.cl', 'status': 'weird'}])

    assert counts['total'] == 1
    assert counts['weird'] == 1


def test_html_carries_every_status(tmp_path):
    """The HTML report shows the same three buckets the JSON does."""
    path = export_html(RESULTS, tmp_path / 'out.html')
    body = path.read_text(encoding='utf-8')

    assert 'ok@nunoa.cl' in body
    assert 'quizas@nunoa.cl' in body
    assert 'no@nunoa.cl' in body


def test_html_escapes_markup_from_crawled_pages(tmp_path):
    """Crawled text reaches the report, so it must never be raw HTML."""
    hostile = [{
        'email': '<script>alert(1)</script>@nunoa.cl',
        'source': 'https://nunoa.cl/"onload="x',
        'status': 'valid',
        'error': '',
    }]
    path = export_html(hostile, tmp_path / 'out.html')
    body = path.read_text(encoding='utf-8')

    assert '<script>alert(1)</script>@nunoa.cl' not in body
    assert '&lt;script&gt;' in body


def test_html_makes_no_external_requests(tmp_path):
    """Self-contained: it has to render with no network and no assets."""
    path = export_html(RESULTS, tmp_path / 'out.html')
    body = path.read_text(encoding='utf-8')

    assert '<link' not in body
    assert 'src=' not in body
    assert 'http://' not in body


def test_html_linkifies_only_http_sources(tmp_path):
    """A javascript: source from a crawled page must not become a link."""
    rows = [{
        'email': 'a@nunoa.cl',
        'source': 'javascript:alert(1)',
        'status': 'valid',
        'error': '',
    }]
    path = export_html(rows, tmp_path / 'out.html')
    body = path.read_text(encoding='utf-8')

    assert 'href="javascript:' not in body


@pytest.mark.parametrize('name,expected', [
    ('out.csv', 'csv'),
    ('out.CSV', 'csv'),
    ('out.json', 'json'),
    ('out.html', 'html'),
    ('out.htm', 'html'),
])
def test_infer_format_reads_the_extension(name, expected):
    """--output out.json should just work, with no second flag."""
    assert infer_format(name) == expected


def test_infer_format_rejects_an_unknown_extension():
    """Failing loudly beats silently writing CSV into a .txt."""
    with pytest.raises(ValueError, match='formato'):
        infer_format('out.txt')


def test_export_dispatches_on_the_extension(tmp_path):
    """The dispatcher is what the CLI and the GUI both go through."""
    path = export(RESULTS, tmp_path / 'out.json')
    payload = json.loads(path.read_text(encoding='utf-8'))

    assert payload['summary']['total'] == 3


def test_explicit_format_overrides_the_extension(tmp_path):
    """--format html --output raro.txt writes HTML, not an error."""
    path = export(RESULTS, tmp_path / 'raro.txt', fmt='html')
    body = path.read_text(encoding='utf-8')

    assert body.startswith('<!DOCTYPE html>')


def test_export_rejects_an_unsupported_format(tmp_path):
    """--format xml is a usage error, not a crash mid-write."""
    with pytest.raises(ValueError, match='xml'):
        export(RESULTS, tmp_path / 'out.csv', fmt='xml')


# ── Chilean-evidence field (ADR-0014)

_WITH_EVIDENCE = [
    {'email': 'a@nunoa.cl', 'source': 'https://nunoa.cl/contacto',
     'status': 'valid', 'error': '', 'evidence': ['lexicon', 'phone-cl']},
    {'email': 'b@nunoa.cl', 'source': 'https://nunoa.cl/otra',
     'status': 'valid', 'error': '', 'evidence': []},
]


def test_csv_ignores_evidence(tmp_path):
    """The mailable deliverable keeps exactly ADR-0010's columns."""
    path = export_valid(_WITH_EVIDENCE, tmp_path / 'out.csv')
    header = path.read_text(encoding='utf-8').splitlines()[0]

    assert header == 'email,source,status,error'
    assert 'evidence' not in path.read_text(encoding='utf-8')


def test_json_carries_evidence(tmp_path):
    """JSON is the run record, so it reports what the page showed."""
    path = export_json(_WITH_EVIDENCE, tmp_path / 'out.json')
    results = json.loads(path.read_text(encoding='utf-8'))['results']

    assert results[0]['evidence'] == ['lexicon', 'phone-cl']


def test_json_omits_evidence_when_nobody_looked(tmp_path):
    """
    Absent and empty must stay distinguishable: empty means the page was
    checked and showed nothing, absent means it was never checked.
    """
    path = export_json(RESULTS, tmp_path / 'out.json')
    results = json.loads(path.read_text(encoding='utf-8'))['results']

    assert 'evidence' not in results[0]

    checked = json.loads(
        export_json(_WITH_EVIDENCE, tmp_path / 'b.json').read_text('utf-8')
    )['results']
    assert checked[1]['evidence'] == []


def test_html_shows_evidence_and_marks_the_empty_case(tmp_path):
    """HTML distinguishes 'checked, nothing found' from 'not checked'."""
    body = export_html(_WITH_EVIDENCE, tmp_path / 'out.html').read_text('utf-8')

    assert '<th>Evidencia</th>' in body
    assert 'lexicon, phone-cl' in body
    assert 'sin-evidencia' in body
    assert 'No afirma la nacionalidad' in body
