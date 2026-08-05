"""
Unit tests for the crawler's bot-wall detection (ADR-0023).

All offline: responses are constructed directly, or served through an
httpx MockTransport, so nothing here touches the network.

Run with: pytest tests/test_crawler.py -v
"""

import asyncio

import httpx

from app.core import crawler as crawler_mod
from app.core.crawler import Crawler, Wall, describe_walls, detect_wall


# The exact body www.aprimin.cl served on 2026-08-05, to every user agent
# tried, under HTTP 202. 169 bytes, no text, one non-http href.
APRIMIN_STUB = (
    '<html><head><link rel="icon" href="data:;"><meta http-equiv="refresh" '
    'content="0;/.well-known/sgcaptcha/?r=%2F&y=ipc:181.42.135.225:'
    '1785903840.628"></meta></head></html>'
)

ORDINARY_PAGE = (
    '<html><body><h1>Contacto</h1>'
    '<p>Escribanos a contacto@ejemplo.cl</p>'
    '<a href="https://ejemplo.cl/equipo">Equipo</a>'
    '</body></html>'
)


def _response(status: int, text: str, headers: dict | None = None) -> httpx.Response:
    """Build a standalone httpx.Response for the detector to judge."""
    return httpx.Response(status, text=text, headers=headers or {})


def test_the_aprimin_stub_is_a_wall_and_names_siteground() -> None:
    """The response that made RadarCL report zero is detected, and named."""
    verdict = detect_wall(_response(202, APRIMIN_STUB))

    assert verdict == Wall(vendor='SiteGround')


def test_a_wall_from_an_unknown_vendor_is_still_a_wall() -> None:
    """
    Shape decides, not the signature list. A vendor nobody here has seen
    must not reproduce the silent zero this ADR exists to prevent.
    """
    stub = '<html><head><meta http-equiv="refresh" content="0;/checking/">' \
           '</head></html>'

    verdict = detect_wall(_response(200, stub))

    assert verdict == Wall(vendor='')


def test_an_ordinary_page_is_not_a_wall() -> None:
    """A short page with readable text and a link is a page."""
    assert detect_wall(_response(200, ORDINARY_PAGE)) is None


def test_a_signature_alone_never_promotes_a_readable_page() -> None:
    """
    A signature supplies the vendor name and nothing else. A page that
    merely mentions the challenge path is still a page.
    """
    page = (
        '<html><body><h1>Como bloqueamos bots</h1>'
        '<p>Usamos /.well-known/sgcaptcha/ para filtrar trafico.</p>'
        '<a href="https://ejemplo.cl/mas">Mas</a></body></html>'
    )

    assert detect_wall(_response(200, page)) is None


def test_a_page_too_large_to_be_a_stub_is_not_a_wall() -> None:
    """Size is part of the test: past a few KB it could be anything."""
    filler = '<div class="x"></div>' * 400

    assert detect_wall(_response(200, f'<html><body>{filler}</body></html>')) is None


def test_a_non_2xx_response_is_not_a_wall() -> None:
    """A 403 already fails the fetch; it is an error, not an unread page."""
    assert detect_wall(_response(403, APRIMIN_STUB)) is None


def test_a_page_offering_a_followable_link_is_not_a_wall() -> None:
    """A link to follow means the crawl can continue, so nothing is lost."""
    stub = '<html><head></head><body><a href="https://ejemplo.cl/x"></a>' \
           '</body></html>'

    assert detect_wall(_response(200, stub)) is None


def test_nothing_blocked_says_nothing() -> None:
    """A clean run must not grow a caveat it has no reason to carry."""
    assert describe_walls([], pages_read=12) == ''


def test_a_fully_walled_site_disclaims_the_zero() -> None:
    """
    The sentence has to carry the whole point, because the count beside it
    reads as a finding otherwise.
    """
    message = describe_walls(
        [('https://www.aprimin.cl', 'SiteGround')], pages_read=0
    )

    assert 'SiteGround' in message
    assert 'no significa que el sitio no tenga correos' in message


def test_an_unrecognised_wall_names_no_vendor() -> None:
    """Empty is 'we do not know who', never a blank pair of brackets."""
    message = describe_walls([('https://otro.cl', '')], pages_read=0)

    assert '()' not in message
    assert 'Ninguna pagina se pudo leer:' in message


def test_a_partly_walled_site_scopes_what_was_found() -> None:
    """Some pages read is not a failed scan, but the gap is still stated."""
    message = describe_walls(
        [('https://mixto.cl/a', 'Cloudflare'), ('https://mixto.cl/b', '')],
        pages_read=30,
    )

    assert '2 paginas no se pudo leer' in message
    assert 'Cloudflare' in message


def test_vendors_are_listed_once_each() -> None:
    """Twenty Cloudflare stubs are one vendor, not twenty."""
    blocked = [(f'https://x.cl/{n}', 'Cloudflare') for n in range(20)]

    assert describe_walls(blocked, pages_read=1).count('Cloudflare') == 1


def _serve(handler):
    """Return an AsyncClient factory whose clients use a mock transport."""
    real = httpx.AsyncClient

    def factory(**kwargs):
        kwargs['transport'] = httpx.MockTransport(handler)
        return real(**kwargs)

    return factory


async def _crawl(crawler: Crawler) -> list[tuple[str, str]]:
    """Drain a crawl into a list of (url, html)."""
    return [page async for page in crawler.crawl()]


def test_a_walled_page_is_reported_and_never_yielded(monkeypatch) -> None:
    """
    The stub must not reach extraction as if it were a page. Reporting it
    is the whole point: an unread page is not a page without addresses.
    """
    monkeypatch.setattr(
        crawler_mod.httpx, 'AsyncClient',
        _serve(lambda request: httpx.Response(202, text=APRIMIN_STUB)),
    )
    blocked: list[tuple[str, str]] = []

    crawler = Crawler(
        seeds=['https://www.aprimin.cl'],
        on_blocked=lambda url, vendor: blocked.append((url, vendor)),
    )
    pages = asyncio.run(_crawl(crawler))

    assert pages == []
    assert blocked == [('https://www.aprimin.cl', 'SiteGround')]


def test_an_ordinary_page_is_yielded_and_not_reported(monkeypatch) -> None:
    """Detection must not cost the crawler a readable page."""
    monkeypatch.setattr(
        crawler_mod.httpx, 'AsyncClient',
        _serve(lambda request: httpx.Response(200, text=ORDINARY_PAGE)),
    )
    blocked: list[tuple[str, str]] = []

    crawler = Crawler(
        seeds=['https://ejemplo.cl'],
        max_depth=0,
        on_blocked=lambda url, vendor: blocked.append((url, vendor)),
    )
    pages = asyncio.run(_crawl(crawler))

    assert [url for url, _ in pages] == ['https://ejemplo.cl']
    assert blocked == []
