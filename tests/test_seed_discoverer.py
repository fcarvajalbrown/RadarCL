"""
Unit tests for seed discovery.

Everything here is offline by default: each Certificate Transparency
source is replaced with a stub and no request leaves the machine. The two
tests that do reach the network carry the `smtp` marker, which in this
project means "needs a live internet connection", so:

    pytest -m "not smtp"        # offline, the default suite
    pytest tests/test_seed_discoverer.py -v

Run with:
    pytest tests/test_seed_discoverer.py -v
"""

import asyncio
import html
import re

import httpx
import pytest

from app.core import seed_discoverer
from app.core.seed_discoverer import (
    CTUnavailable,
    EntityType,
    _certspotter_subdomains,
    _crtsh_subdomains,
    _ct_subdomains,
    _KNOWN_SOURCES,
    detect_entity_type,
    discover_seeds,
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

    def __init__(self, status_code: int, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload

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


# ── Curated sources

def test_every_entity_type_has_curated_sources() -> None:
    """No entity type may fall through stage 4 with nothing."""
    for entity_type in EntityType:
        assert _KNOWN_SOURCES.get(entity_type), entity_type


def test_every_source_declares_an_identity_phrase() -> None:
    """
    A URL with no phrase is a source nothing can check.

    The mapping shape makes this hard to get wrong, which is the point of
    using one, but the guard is cheap and the cost of a missing phrase is
    a source that silently goes unverified for years.
    """
    for entity_type, sources in _KNOWN_SOURCES.items():
        for url, phrase in sources.items():
            assert phrase.strip(), f"{entity_type}: {url} has no phrase"
            assert phrase == phrase.lower(), (
                f"{url}: {phrase!r} must be lowercase, since matching is"
                f" done against lowercased text"
            )


def test_identity_phrases_are_not_trivially_generic() -> None:
    """
    A phrase has to be specific enough to die with a change of owner.

    'contacto' or 'chile' would survive munitel.cl becoming a property
    site, which would make the guard worse than useless: it would report
    green while the crawler indexed apartment listings.
    """
    too_generic = {
        'chile', 'contacto', 'inicio', 'gobierno', 'portal', 'sitio',
        'home', 'noticias', 'servicios',
    }
    for sources in _KNOWN_SOURCES.values():
        for url, phrase in sources.items():
            assert phrase not in too_generic, f"{url}: {phrase!r}"


def test_a_repeated_source_declares_one_identity() -> None:
    """
    portaltransparencia.cl appears under two entity types.

    Two entity types disagreeing about what a URL is means one of them is
    wrong, and the live check would then pass or fail depending on which
    entry it happened to read.
    """
    seen: dict[str, str] = {}
    for sources in _KNOWN_SOURCES.values():
        for url, phrase in sources.items():
            assert seen.setdefault(url, phrase) == phrase, url


def test_removed_sources_stay_removed() -> None:
    """
    Four entries had rotted into something else and were taken out.

    transparencia.cl is a content blog rather than the state portal,
    munitel.cl is a real-estate site, cna.cl is an arbitration centre
    rather than the accreditation commission, and fach.cl is the Air
    Force. Re-adding any of them by pattern-matching on the name is an
    easy mistake to make twice.
    """
    hosts = {
        url for urls in _KNOWN_SOURCES.values() for url in urls
    }
    for gone in (
        'https://www.transparencia.cl',
        'https://www.munitel.cl',
        'https://www.cna.cl',
        'https://www.fach.cl',
    ):
        assert gone not in hosts


def test_municipality_detection_still_precedes_keywords() -> None:
    """The curated lists are only reached through entity detection."""
    assert detect_entity_type('nunoa.cl') is EntityType.MUNICIPALITY
    assert detect_entity_type('minsal.cl') is EntityType.GOVERNMENT
    assert detect_entity_type('usach.cl') is EntityType.UNIVERSITY
    # The Biblioteca del Congreso Nacional is a government body. It read as
    # a company until 'bcn' was added to the keyword table, which meant a
    # scan of it got the company sources rather than the government ones.
    assert detect_entity_type('bcn.cl') is EntityType.GOVERNMENT


# ── Live checks, skipped offline

def _visible_text(markup: str) -> str:
    """
    Reduce a page to the text a reader would see, lowercased.

    Scripts and styles go first, because an analytics snippet or a CSS
    rule can carry a word the page itself no longer says. Entities are
    unescaped so a phrase can be written with its accents rather than as
    `informaci&oacute;n`.
    """
    stripped = re.sub(
        r'<script.*?</script>|<style.*?</style>', '', markup,
        flags=re.S | re.I,
    )
    text = html.unescape(re.sub(r'<[^>]+>', ' ', stripped))
    return re.sub(r'\s+', ' ', text).lower()


@pytest.mark.smtp
def test_curated_sources_are_still_themselves() -> None:
    """
    Every curated source still answers, and still says who it is.

    Reachability alone is not enough and this is not hypothetical:
    munitel.cl kept answering 200 for however long it took to become a
    real-estate portal, and a status-code check would have passed it every
    day. So each source declares a phrase that names the institution, and
    the phrase has to still be on the page.

    The two failures are reported separately because they need different
    responses. UNREACHABLE may be the network, and is retried once, since
    subdere.gov.cl threw a transient RemoteProtocolError while this was
    being written and answered on the next call. DRIFTED is never
    transient: the page loaded and is no longer the thing it was, so go
    read it before touching the URL.
    """
    async def _fetch(client, url: str):
        resp = await client.get(url, timeout=20.0)
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}")
        return resp.text

    async def _check() -> list[str]:
        problems: list[str] = []
        sources = {
            url: phrase
            for mapping in _KNOWN_SOURCES.values()
            for url, phrase in mapping.items()
        }
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": seed_discoverer._USER_AGENT},
        ) as client:
            for url, phrase in sorted(sources.items()):
                try:
                    markup = await _fetch(client, url)
                except Exception:
                    try:
                        markup = await _fetch(client, url)
                    except Exception as exc:
                        problems.append(
                            f"UNREACHABLE {url}: {type(exc).__name__}: {exc}"
                        )
                        continue

                if phrase not in _visible_text(markup):
                    problems.append(
                        f"DRIFTED {url}: the page no longer says "
                        f"{phrase!r}. Read it before editing the URL - it "
                        f"may have become a different organisation."
                    )
        return problems

    problems = asyncio.run(_check())
    # Spelled out rather than left to `== []`, because the whole value of
    # this check is the sentence naming which source went wrong and how.
    assert not problems, "\n" + "\n".join(problems)


@pytest.mark.smtp
def test_certspotter_still_returns_the_documented_shape() -> None:
    """
    The fallback is only worth having if its response shape holds.

    Accepts a 429 as a pass: ten full-domain queries an hour is the
    unauthenticated allowance, and a shared address can exhaust it.
    """
    async def _query():
        async with httpx.AsyncClient(
            headers={"User-Agent": seed_discoverer._USER_AGENT},
        ) as client:
            return await _certspotter_subdomains('nunoa.cl', client)

    try:
        found = asyncio.run(_query())
    except CTUnavailable as exc:
        if '429' in str(exc):
            pytest.skip("Cert Spotter rate limit reached")
        raise

    assert all(host.endswith('nunoa.cl') for host in found)
