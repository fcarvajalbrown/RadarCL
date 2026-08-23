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


def _counting_fetch(peak: list[int], started: list[str], delay: float = 0.05):
    """
    Build a `_fetch` replacement that records how many run at once.

    Replaces the fetch rather than the transport so the test measures the
    crawl loop and touches no HTTP stack at all.
    """
    inflight = [0]

    async def fetch(self, client, url):
        started.append(url)
        inflight[0] += 1
        peak[0] = max(peak[0], inflight[0])
        await asyncio.sleep(delay)
        inflight[0] -= 1
        return ORDINARY_PAGE

    return fetch


def test_requests_run_concurrently(monkeypatch) -> None:
    """
    The declared concurrency is the number of requests actually in flight.

    Before ADR-0025 this peaked at 1 for every value, because the loop
    awaited each fetch inline and the semaphore never had a second waiter.
    """
    peak, started = [0], []
    monkeypatch.setattr(Crawler, '_fetch', _counting_fetch(peak, started))

    crawler = Crawler(
        seeds=[f'https://ejemplo.cl/{n}' for n in range(6)],
        max_depth=0,
        concurrency=3,
    )
    pages = asyncio.run(_crawl(crawler))

    assert len(pages) == 6
    assert peak[0] == 3


def test_concurrency_one_stays_serial(monkeypatch) -> None:
    """One is a real setting, not the only behaviour available."""
    peak, started = [0], []
    monkeypatch.setattr(Crawler, '_fetch', _counting_fetch(peak, started))

    crawler = Crawler(
        seeds=[f'https://ejemplo.cl/{n}' for n in range(4)],
        max_depth=0,
        concurrency=1,
    )
    pages = asyncio.run(_crawl(crawler))

    assert len(pages) == 4
    assert peak[0] == 1


def test_the_page_cap_bounds_requests_not_just_results(monkeypatch) -> None:
    """
    Six seeds and a cap of two must not cost six requests.

    With several fetches in flight the cap has to be checked before
    dispatch; checking it only on the way out would pay for four pages
    nobody sees.
    """
    peak, started = [0], []
    monkeypatch.setattr(Crawler, '_fetch', _counting_fetch(peak, started))

    crawler = Crawler(
        seeds=[f'https://ejemplo.cl/{n}' for n in range(6)],
        max_depth=0,
        concurrency=5,
        max_pages=2,
    )
    pages = asyncio.run(_crawl(crawler))

    assert len(pages) == 2
    assert len(started) == 2


def test_pausing_stops_new_requests(monkeypatch) -> None:
    """
    A pause holds the frontier and dispatches nothing while it lasts.

    Requests already in flight are not cancelled: the response has been
    paid for, and throwing it away buys nothing.
    """
    peak, started = [0], []
    monkeypatch.setattr(Crawler, '_fetch', _counting_fetch(peak, started, 0.0))

    async def scenario():
        crawler = Crawler(
            seeds=[f'https://ejemplo.cl/{n}' for n in range(3)],
            max_depth=0,
            concurrency=2,
        )
        crawler.pause()

        pages = []

        async def consume():
            async for page in crawler.crawl():
                pages.append(page)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        while_paused = list(started)

        crawler.resume()
        await asyncio.wait_for(task, 2)
        return while_paused, pages

    while_paused, pages = asyncio.run(scenario())

    assert while_paused == []
    assert len(pages) == 3


def test_closing_the_crawl_cancels_requests_in_flight(monkeypatch) -> None:
    """
    A consumer that stops must not leave requests running behind it.

    `should_stop` in the pipeline breaks out of the loop, which closes this
    generator; whatever was still outstanding is cancelled there.
    """
    cancelled: list[str] = []

    async def fetch(self, client, url):
        if url.endswith('/0'):
            return ORDINARY_PAGE
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.append(url)
            raise
        return ORDINARY_PAGE

    monkeypatch.setattr(Crawler, '_fetch', fetch)

    async def scenario():
        crawler = Crawler(
            seeds=[f'https://ejemplo.cl/{n}' for n in range(3)],
            max_depth=0,
            concurrency=3,
        )
        pages = crawler.crawl()
        async for _ in pages:
            break
        await pages.aclose()
        await asyncio.sleep(0.01)

    asyncio.run(scenario())

    assert sorted(cancelled) == [
        'https://ejemplo.cl/1', 'https://ejemplo.cl/2',
    ]


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
