"""
Async HTTP crawler using httpx.

Phase 1: restricts crawl to .cl domains only.
Phase 2 (optional): follows external links found on .cl pages,
         but email filter always remains .cl-only.
"""

import asyncio
from typing import AsyncGenerator, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


def is_cl_domain(url: str) -> bool:
    """Return True if the URL host ends with .cl."""
    host = urlparse(url).netloc.lower().split(':')[0]
    parts = host.split('.')
    return len(parts) >= 2 and parts[-1] == 'cl'


class Crawler:
    """
    Async crawler that yields (page_url, html) tuples.

    Parameters
    ----------
    seeds : list[str]
        Starting URLs.
    phase2_enabled : bool
        If True, follow non-.cl links after phase1_timeout seconds.
    phase1_timeout : float | None
        Seconds before Phase 2 activates. None = never.
    max_pages : int
        Hard cap on total pages crawled.
    max_depth : int
        Maximum link-follow depth from seeds.
    concurrency : int
        Simultaneous HTTP requests.
    respect_robots : bool
        Placeholder — not yet implemented.
    """

    def __init__(
        self,
        seeds: list[str],
        phase2_enabled: bool = False,
        phase1_timeout: float | None = None,
        max_pages: int = 5000,
        max_depth: int = 3,
        concurrency: int = 10,
        respect_robots: bool = False,
    ) -> None:
        self.seeds = seeds
        self.phase2_enabled = phase2_enabled
        self.phase1_timeout = phase1_timeout
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.respect_robots = respect_robots
        self._visited: Set[str] = set()
        self._pages_crawled: int = 0
        self._phase2_active: bool = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()
    
    def pause(self) -> None:
        """Pause the crawler by clearing the pause event."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume the crawler by setting the pause event."""
        self._pause_event.set()

    async def crawl(self) -> AsyncGenerator[tuple[str, str], None]:
        """Yield (url, html) for each successfully fetched page."""
        queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        for seed in self.seeds:
            await queue.put((seed, 0))

        semaphore = asyncio.Semaphore(self.concurrency)
        start_time = asyncio.get_event_loop().time()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": "RadarCL/0.1"},
        ) as client:
            while not queue.empty() and self._pages_crawled < self.max_pages:
                if (
                    self.phase2_enabled
                    and self.phase1_timeout is not None
                    and not self._phase2_active
                    and (asyncio.get_event_loop().time() - start_time) >= self.phase1_timeout
                ):
                    self._phase2_active = True

                url, depth = await queue.get()
                # Block here if paused, resuming when event is set
                await self._pause_event.wait()
                if url in self._visited or depth > self.max_depth:
                    continue
                self._visited.add(url)

                if not self._phase2_active and not is_cl_domain(url):
                    continue

                async with semaphore:
                    html = await self._fetch(client, url)
                if html is None:
                    continue

                self._pages_crawled += 1
                yield url, html

                if depth < self.max_depth:
                    for link in self._extract_links(html, url):
                        if link not in self._visited:
                            await queue.put((link, depth + 1))

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        """Fetch a URL and return HTML, or None on failure."""
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except Exception:
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