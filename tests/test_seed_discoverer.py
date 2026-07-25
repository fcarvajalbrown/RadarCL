"""
Unit tests for seed discovery.

Everything here is offline by default: each Certificate Transparency
source is replaced with a stub and no request leaves the machine. The one
test that does reach the network carries the `smtp` marker, which in this
project means "needs a live internet connection", so:

    pytest -m "not smtp"        # offline, the default suite
    pytest tests/test_seed_discoverer.py -v

Run with:
    pytest tests/test_seed_discoverer.py -v
"""

import asyncio

import httpx
import pytest

from app.core import seed_discoverer
from app.core.crawler import USER_AGENT
from app.core.seed_discoverer import (
    CTUnavailable,
    _certspotter_subdomains,
    _crtsh_subdomains,
    _ct_subdomains,
    _semantic_seeds_from_url,
    detect_entity_type,
    discover_seeds,
    EntityType,
)


def _fail(message: str):
    """Build a CT source stub that errors."""
    async def _source(domain: str, client) -> list[str]:
        raise CTUnavailable(message)
    return _source


def _answer(*names: str):
    """Build a CT source stub that answers, possibly with nothing."""
    async def _source(domain: str, client) -> list[str]:
        return list(names)
    return _source


async def _never_runs(domain: str, client) -> list[str]:
    raise AssertionError("the fallback source must not run")


def _patch_chain(monkeypatch, crtsh, certspotter) -> None:
    """Replace the two sources _ct_subdomains tries in order."""
    monkeypatch.setattr(seed_discoverer, '_crtsh_subdomains', crtsh)
    monkeypatch.setattr(seed_discoverer, '_certspotter_subdomains', certspotter)


def _chain(monkeypatch, crtsh, certspotter) -> list[str]:
    """Run the chain against stubs and return what it produced."""
    _patch_chain(monkeypatch, crtsh, certspotter)
    return asyncio.run(_ct_subdomains('nunoa.cl', None))


# ── The fallback chain

def test_crtsh_answers_so_certspotter_never_runs(monkeypatch) -> None:
    """A non-empty first result stops the chain."""
    found = _chain(
        monkeypatch, _answer('mail.nunoa.cl', 'webmail.nunoa.cl'), _never_runs
    )
    assert found == ['mail.nunoa.cl', 'webmail.nunoa.cl']


def test_falls_back_when_crtsh_errors(monkeypatch) -> None:
    """
    A crt.sh outage no longer costs the whole stage.

    This is the case that produced the change: crt.sh answered 502 for
    about fifteen minutes, and stage 1 silently returned nothing.
    """
    found = _chain(
        monkeypatch,
        _fail('crt.sh HTTP 502'),
        _answer('serviciosenlinea.nunoa.cl'),
    )
    assert found == ['serviciosenlinea.nunoa.cl']


def test_falls_back_when_crtsh_answers_empty(monkeypatch) -> None:
    """An empty answer is not good enough to stop the chain."""
    found = _chain(
        monkeypatch, _answer(), _answer('serviciosenlinea.nunoa.cl')
    )
    assert found == ['serviciosenlinea.nunoa.cl']


def test_every_source_empty_returns_empty(monkeypatch) -> None:
    """
    Both sources answering with no records is an answer, not a failure.

    A domain can genuinely have no logged certificates. Raising here would
    conflate that with being unable to ask, which is the distinction
    ADR-0009 drew for DNS and ADR-0011 carries over.
    """
    assert _chain(monkeypatch, _answer(), _answer()) == []


def test_every_source_failing_raises(monkeypatch) -> None:
    """Exhausting every source is indeterminate, and says why."""
    _patch_chain(
        monkeypatch, _fail('crt.sh HTTP 502'), _fail('certspotter HTTP 429')
    )
    with pytest.raises(CTUnavailable) as exc:
        asyncio.run(_ct_subdomains('nunoa.cl', None))

    # The combined message keeps each source's reason for diagnosis.
    assert 'crt.sh HTTP 502' in str(exc.value)
    assert 'certspotter HTTP 429' in str(exc.value)


# ── Response parsing

class _Response:
    """Minimal httpx.Response stand-in."""

    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def _client_returning(response: _Response):
    """Build a client stub whose every GET returns `response`."""
    class _Client:
        @staticmethod
        async def get(*args, **kwargs):
            return response
    return _Client()


def test_crtsh_splits_multiline_name_values() -> None:
    """
    crt.sh packs several names into one newline-separated field.

    Wildcards and names outside the target domain are dropped, and a name
    repeated across certificates appears once.
    """
    payload = [
        {'name_value': 'nunoa.cl\nwww.nunoa.cl\n*.nunoa.cl'},
        {'name_value': 'MAIL.NUNOA.CL\nwww.nunoa.cl'},
        {'name_value': 'unrelated.example.com'},
    ]
    found = asyncio.run(
        _crtsh_subdomains('nunoa.cl', _client_returning(_Response(200, payload)))
    )
    assert found == ['nunoa.cl', 'www.nunoa.cl', 'mail.nunoa.cl']


def test_certspotter_reads_dns_names() -> None:
    """Cert Spotter returns an array per issuance, deduplicated here."""
    payload = [
        {'dns_names': ['serviciosenlinea.nunoa.cl', 'www.serviciosenlinea.nunoa.cl']},
        {'dns_names': ['nunoa.cl', 'www.nunoa.cl']},
        {'dns_names': ['nunoa.cl', '*.nunoa.cl', 'nunoa.cl.evil.example']},
        {},
    ]
    found = asyncio.run(
        _certspotter_subdomains(
            'nunoa.cl', _client_returning(_Response(200, payload))
        )
    )
    assert found == [
        'serviciosenlinea.nunoa.cl',
        'www.serviciosenlinea.nunoa.cl',
        'nunoa.cl',
        'www.nunoa.cl',
    ]


def test_certspotter_rate_limit_is_a_failure_not_an_empty_answer() -> None:
    """
    429 means the question was refused, so it must not read as "no records".

    Ten full-domain queries an hour is the unauthenticated allowance, and
    an eleventh returns 429. Treating that as an empty answer would stop
    the chain on a source that never looked.
    """
    with pytest.raises(CTUnavailable) as exc:
        asyncio.run(
            _certspotter_subdomains(
                'nunoa.cl', _client_returning(_Response(429))
            )
        )
    assert '429' in str(exc.value)


def test_crtsh_non_200_is_a_failure() -> None:
    """502 is what crt.sh actually returns when it is down."""
    with pytest.raises(CTUnavailable) as exc:
        asyncio.run(
            _crtsh_subdomains('nunoa.cl', _client_returning(_Response(502)))
        )
    assert '502' in str(exc.value)


# ── The stage still fails silently

def test_discover_seeds_survives_total_ct_failure(monkeypatch) -> None:
    """
    Stage 1 collapsing must not take the pipeline with it.

    The cascade's whole design is that a dead source costs its own stage
    and nothing more, so seeds still come back from the base domain.
    """
    _patch_chain(monkeypatch, _fail('crt.sh down'), _fail('certspotter down'))

    async def _live(subdomains, client):
        return [f"https://{host}" for host in subdomains]

    async def _no_links(base_url, domain, entity_type, client):
        return []

    monkeypatch.setattr(seed_discoverer, '_verify_subdomains', _live)
    monkeypatch.setattr(seed_discoverer, '_semantic_seeds_from_url', _no_links)

    seeds = asyncio.run(discover_seeds('nunoa.cl', use_duckduckgo=False))
    assert 'https://nunoa.cl' in seeds
    assert 'https://www.nunoa.cl' in seeds


# ── Link scoring

def _page(markup: str):
    """Build a client stub whose every GET returns `markup`."""
    class _Client:
        @staticmethod
        async def get(*args, **kwargs):
            return _Response(200, text=markup)
    return _Client()


def _links(markup: str, domain: str = 'nunoa.cl') -> list[str]:
    """Score a page's links and return the URLs kept, best first."""
    scored = asyncio.run(
        _semantic_seeds_from_url(
            f"https://{domain}/", domain, EntityType.MUNICIPALITY,
            _page(markup),
        )
    )
    return [url for _, url in scored]


def test_scoring_keeps_relevant_internal_links() -> None:
    """The entity scoring table decides, and ranks what it keeps."""
    kept = _links(
        '<a href="/transparencia/funcionarios">f</a>'
        '<a href="/contacto">c</a>'
        '<a href="/programas">p</a>'
        '<a href="/noticias/2026">n</a>'
    )
    # 'funcionarios' and 'contacto' both score 10, 'programas' 3, and
    # 'noticias' is not in either table so it never reaches the list.
    assert 'https://nunoa.cl/noticias/2026' not in kept
    assert set(kept) == {
        'https://nunoa.cl/transparencia/funcionarios',
        'https://nunoa.cl/contacto',
        'https://nunoa.cl/programas',
    }
    assert kept[-1] == 'https://nunoa.cl/programas'


def test_an_offsite_link_naming_the_domain_is_not_internal() -> None:
    """
    The domain has to be in the host, not just somewhere in the URL.

    The curated-source stage used to seed institutional sites and matched
    their links on the domain appearing anywhere in the URL, so a tracking
    or referrer parameter read as an internal page. That stage is gone
    (ADR-0013) and the loose match went with it.
    """
    kept = _links(
        '<a href="https://example.com/contacto?ref=nunoa.cl">x</a>'
        '<a href="https://www.nunoa.cl/contacto">y</a>'
    )
    assert kept == ['https://www.nunoa.cl/contacto']


def test_municipality_detection_still_precedes_keywords() -> None:
    """
    Entity type still decides which scoring table and queries are used.

    It stopped selecting a curated source list when that stage was removed
    (ADR-0013), but the link scoring and the DuckDuckGo queries both still
    read it, so a domain landing in the wrong type is still a real
    misdetection.
    """
    assert detect_entity_type('nunoa.cl') is EntityType.MUNICIPALITY
    assert detect_entity_type('minsal.cl') is EntityType.GOVERNMENT
    assert detect_entity_type('usach.cl') is EntityType.UNIVERSITY
    # The Biblioteca del Congreso Nacional is a government body. It read as
    # a company until 'bcn' was added to the keyword table.
    assert detect_entity_type('bcn.cl') is EntityType.GOVERNMENT


# ── Live checks, skipped offline

@pytest.mark.smtp
def test_certspotter_still_returns_the_documented_shape() -> None:
    """
    The fallback is only worth having if its response shape holds.

    Accepts a 429 as a pass: ten full-domain queries an hour is the
    unauthenticated allowance, and a shared address can exhaust it.
    """
    async def _query():
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
        ) as client:
            return await _certspotter_subdomains('nunoa.cl', client)

    try:
        found = asyncio.run(_query())
    except CTUnavailable as exc:
        if '429' in str(exc):
            pytest.skip("Cert Spotter rate limit reached")
        raise

    assert all(host.endswith('nunoa.cl') for host in found)
