"""
Async HTTP crawler using httpx.

Phase 1: restricts crawl to .cl domains only.
Phase 2 (optional): follows external links found on .cl pages,
         but email filter always remains .cl-only.
"""

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core import scope


# Sent by every request RadarCL makes, crawling and seed discovery alike.
# `portaltransparencia.cl` and `anid.cl` answer 403 to a bare tool token
# and 200 to this one, so a stage that seeded them handed the crawler two
# URLs it could not open. It lives here rather than in `seed_discoverer`
# because this is the lower-level module of the two, and it is one
# constant rather than two so the pair cannot drift (ADR-0013).
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


_MAX_WALL_BYTES = 2048

_WALL_SIGNATURES: tuple[tuple[str, str], ...] = (
    ('/.well-known/sgcaptcha/', 'SiteGround'),
    ('/.well-known/captcha/', 'SiteGround'),
    ('cdn-cgi/challenge-platform', 'Cloudflare'),
    ('__cf_chl', 'Cloudflare'),
    ('just a moment', 'Cloudflare'),
    ('_incapsula_resource', 'Imperva'),
    ('ddos-guard', 'DDoS-Guard'),
    ('sucuri_cloudproxy', 'Sucuri'),
)

_WALL_HEADERS: tuple[tuple[str, str], ...] = (
    ('cf-mitigated', 'Cloudflare'),
    ('x-sucuri-block', 'Sucuri'),
)


@dataclass(frozen=True)
class Wall:
    """
    A response that was fetched but could not be read.

    Attributes
    ----------
    vendor : str
        Name of the recognised anti-bot vendor, or '' when the shape says
        blocked and no signature matched. Empty is a real answer meaning
        the wall is unrecognised, not that there is no wall.
    """
    vendor: str = ''


def _has_followable_link(soup: BeautifulSoup) -> bool:
    """Return True if the page offers any link the crawler could follow."""
    for tag in soup.find_all('a', href=True):
        href = str(tag['href']).strip()
        if not href or href.startswith('#'):
            continue
        if urlparse(href).scheme in ('', 'http', 'https'):
            return True
    return False


def _wall_vendor(resp: httpx.Response, body: str) -> str:
    """Name the anti-bot vendor behind a blocked response, '' if unknown."""
    for header, name in _WALL_HEADERS:
        if header in resp.headers:
            return name

    lowered = body.lower()
    for needle, name in _WALL_SIGNATURES:
        if needle in lowered:
            return name

    return ''


def detect_wall(resp: httpx.Response) -> Wall | None:
    """
    Judge whether a fetched response is a page or an unread wall.

    A wall answers 2xx, so `raise_for_status` waves it through, and then
    carries nothing: no readable text and no followable link. Reporting it
    as a page with no addresses asserts an absence nobody observed, which
    is the inference ADR-0009, ADR-0014 and ADR-0017 already refuse
    elsewhere.

    Parameters
    ----------
    resp : httpx.Response

    Returns
    -------
    Wall | None
        None when the response is a readable page.
    """
    if not 200 <= resp.status_code < 300:
        return None

    body = resp.text
    if len(body) > _MAX_WALL_BYTES:
        return None

    soup = BeautifulSoup(body, 'lxml')
    if soup.get_text(strip=True):
        return None
    if _has_followable_link(soup):
        return None

    return Wall(vendor=_wall_vendor(resp, body))


def describe_walls(blocked: list[tuple[str, str]], pages_read: int) -> str:
    """
    Phrase what a run of unreadable pages means, in the reader's terms.

    Lives here rather than in a caller so the CLI and the GUI say the same
    thing, the way `pipeline` holds one implementation of each loop.

    Parameters
    ----------
    blocked : list[tuple[str, str]]
        (url, vendor) per unreadable page. Vendor '' means unrecognised.
    pages_read : int
        Pages that were read. Zero changes the claim entirely: the scan
        observed no absence, so the count beside it says nothing about the
        site (ADR-0023).

    Returns
    -------
    str
        Empty when nothing was blocked, so a clean run grows no caveat.
    """
    if not blocked:
        return ''

    vendors = sorted({vendor for _, vendor in blocked if vendor})
    named = f" ({', '.join(vendors)})" if vendors else ''

    if pages_read:
        plural = 's' if len(blocked) > 1 else ''
        return (
            f"{len(blocked)} pagina{plural} no se pudo leer{named}. "
            f"Lo encontrado no cubre esa parte del sitio."
        )

    return (
        f"Ninguna pagina se pudo leer{named}: el sitio respondio con un "
        f"desafio anti-bot o una pagina vacia. El resultado no significa "
        f"que el sitio no tenga correos."
    )


def is_cl_domain(url: str) -> bool:
    """Return True if the URL host ends with .cl."""
    return scope.host_in_scope(url)


class Crawler:
    """
    Async crawler that yields (page_url, html) tuples.

    Parameters
    ----------
    seeds : list[str]
        Starting URLs.
    target_domain : str
        Bare lowercase target domain. Phase 1 follows links on `.cl` hosts
        and on this domain. Without it a `bhp.com` seed is fetched, all of
        its links are discarded for being off-`.cl`, the frontier empties
        and the crawl ends having read one page (ADR-0024).
    phase2_enabled : bool
        If True, follow links outside that scope after phase1_timeout
        seconds.
    phase1_timeout : float | None
        Seconds before Phase 2 activates. None = never.
    max_pages : int
        Hard cap on total pages crawled.
    max_depth : int
        Maximum link-follow depth from seeds.
    concurrency : int
        Simultaneous HTTP requests, and the real number of them since
        [ADR-0025](../../docs/adr/0025-concurrency-is-real-and-the-user-sets-it.md).
        Until then `crawl` awaited each fetch inline, so the semaphore it
        built never had a second waiter and every crawl was serial whatever
        the hardware profile declared.
    respect_robots : bool
        Placeholder — not yet implemented.
    on_blocked : Callable[[str, str], None] | None
        Called with (url, vendor) for each page that was fetched but could
        not be read. Vendor is '' when the wall is unrecognised. A blocked
        page is never yielded, and a caller that does not hear about it
        would report an absence nobody observed (ADR-0023).
    """

    def __init__(
        self,
        seeds: list[str],
        target_domain: str = '',
        phase2_enabled: bool = False,
        phase1_timeout: float | None = None,
        max_pages: int = 5000,
        max_depth: int = 3,
        concurrency: int = 10,
        respect_robots: bool = False,
        pause_event: asyncio.Event | None = None,
        on_blocked: Callable[[str, str], None] | None = None,
    ) -> None:
        self.seeds = seeds
        self.target_domain = scope.normalise(target_domain)
        self.phase2_enabled = phase2_enabled
        self.phase1_timeout = phase1_timeout
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.respect_robots = respect_robots
        self._on_blocked = on_blocked
        self._visited: Set[str] = set()
        self._pages_crawled: int = 0
        self._pages_blocked: int = 0
        self._phase2_active: bool = False
        self._pause_event = pause_event or asyncio.Event()
        self._pause_event.set()
    
    def pause(self) -> None:
        """Pause the crawler by clearing the pause event."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume the crawler by setting the pause event."""
        self._pause_event.set()

    async def crawl(self) -> AsyncGenerator[tuple[str, str], None]:
        """
        Yield (url, html) for each successfully fetched page.

        Up to `concurrency` fetches are in flight at once, and a page is
        yielded as it arrives rather than in frontier order, so two runs of
        the same scan can report the same pages in a different sequence
        (ADR-0025).

        Pausing stops new requests from being dispatched and lets the ones
        already in flight finish; there is nothing useful to do with a
        response that has already been paid for. Closing the generator -
        which is what a consumer's `break` does - cancels whatever is still
        outstanding.
        """
        frontier: deque[tuple[str, int]] = deque((seed, 0) for seed in self.seeds)
        pending: set[asyncio.Task] = set()
        start_time = asyncio.get_event_loop().time()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            try:
                while (frontier or pending) and self._pages_crawled < self.max_pages:
                    await self._pause_event.wait()
                    self._maybe_start_phase2(start_time)

                    while (
                        frontier
                        and len(pending) < self.concurrency
                        and self._pages_crawled + len(pending) < self.max_pages
                    ):
                        url, depth = frontier.popleft()
                        if not self._claim(url, depth):
                            continue
                        pending.add(asyncio.create_task(
                            self._fetch_page(client, url, depth)
                        ))

                    if not pending:
                        break

                    done, pending = await asyncio.wait(
                        pending, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        url, depth, html = task.result()
                        if html is None:
                            continue

                        self._pages_crawled += 1
                        yield url, html

                        if depth < self.max_depth:
                            for link in self._extract_links(html, url):
                                if link not in self._visited:
                                    frontier.append((link, depth + 1))
                        if self._pages_crawled >= self.max_pages:
                            break
            finally:
                for task in pending:
                    task.cancel()

    def _maybe_start_phase2(self, start_time: float) -> None:
        """Widen the crawl past phase-1 scope once phase1_timeout has passed."""
        if self._phase2_active or not self.phase2_enabled:
            return
        if self.phase1_timeout is None:
            return
        if (asyncio.get_event_loop().time() - start_time) >= self.phase1_timeout:
            self._phase2_active = True

    def _claim(self, url: str, depth: int) -> bool:
        """
        Mark a URL as visited and say whether it may be fetched now.

        A URL phase 1 declines is still marked, so the same off-scope link
        found on fifty pages is judged once rather than fifty times.
        """
        if url in self._visited or depth > self.max_depth:
            return False
        self._visited.add(url)
        if self._phase2_active:
            return True
        return scope.host_in_scope(url, self.target_domain) or url in self.seeds

    async def _fetch_page(
        self, client: httpx.AsyncClient, url: str, depth: int
    ) -> tuple[str, int, str | None]:
        """Fetch one URL, carrying its depth back alongside the result."""
        return url, depth, await self._fetch(client, url)

    @property
    def pages_blocked(self) -> int:
        """Count of pages fetched successfully that could not be read."""
        return self._pages_blocked

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        """
        Fetch a URL and return HTML, or None if nothing readable came back.

        A wall and a transport error both yield None, because the crawler
        can do nothing with either. They are not the same thing to the
        caller, so a wall is reported through `on_blocked` first.
        """
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except Exception:
            return None

        wall = detect_wall(resp)
        if wall is None:
            return resp.text

        self._pages_blocked += 1
        if self._on_blocked is not None:
            self._on_blocked(url, wall.vendor)
        return None

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract and resolve all <a href> links from HTML."""
        soup = BeautifulSoup(html, 'lxml')
        links = []
        for tag in soup.find_all('a', href=True):
            full = urljoin(base_url, tag['href'].strip()) # type: ignore
            parsed = urlparse(full)
            if parsed.scheme in ('http', 'https'):
                links.append(full)
        return links