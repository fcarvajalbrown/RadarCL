"""
QThread worker that runs the async crawler and emits discovered
emails back to the GUI thread via Qt signals.

Conservative defaults for low-spec hardware (Dell Optiplex etc.):
  - concurrency: 3 simultaneous requests
  - request delay: 0.5s between fetches
  - bounded email queue to avoid RAM growth
"""

import asyncio
from PySide6.QtCore import QThread, Signal

from app.core.crawler import Crawler
from app.core.extractor import extract_emails
from app.core.pattern_generator import generate_candidates


class CrawlerWorker(QThread):
    """
    Runs the crawl + extraction pipeline in a background thread.

    Signals
    -------
    email_found : Signal(str, str)
        Emitted for each discovered email: (email_address, source_url).
    candidate_found : Signal(str, str)
        Emitted for each pattern-generated candidate: (email, source_url).
    debug_message : Signal(str)
        Emitted for crawler debug messages (URLs visited, errors).
    crawl_finished : Signal()
        Emitted when the crawl completes or is stopped.
    """

    email_found: Signal = Signal(str, str)
    candidate_found: Signal = Signal(str, str)
    debug_message: Signal = Signal(str)
    page_crawled: Signal = Signal(int)
    crawl_finished: Signal = Signal()

    def __init__(
        self,
        seeds: list[str],
        target_domain: str,
        phase2_enabled: bool,
        phase1_timeout: float | None,
        max_pages: int = 2000,
        respect_robots: bool = False,
        pattern: str = "",
        request_delay: float = 0.5,
        concurrency: int = 3,
        pause_event: asyncio.Event | None = None,
    ) -> None:
        """
        Initialise the crawler worker.

        Parameters
        ----------
        seeds : list[str]
            Starting URLs.
        target_domain : str
            Target email domain (e.g. @bhp.cl). Empty = any .cl.
        phase2_enabled : bool
        phase1_timeout : float | None
        max_pages : int
            Hard cap — kept low for old hardware.
        respect_robots : bool
        pattern : str
            Optional email pattern (e.g. {first}.{last}).
        request_delay : float
            Seconds to wait between requests. Default 0.5s.
        concurrency : int
            Simultaneous requests. Default 3 for low-spec machines.
        pause_event : asyncio.Event | None
            External pause event. If None, a new one is created.
        """
        super().__init__()
        self._seeds = seeds
        self._target = target_domain.lower().lstrip('@') if target_domain else None
        self._phase2_enabled = phase2_enabled
        self._phase1_timeout = phase1_timeout
        self._max_pages = max_pages
        self._respect_robots = respect_robots
        self._pattern = pattern
        self._request_delay = request_delay
        self._concurrency = concurrency
        self._stop_flag = False
        self._pause_event = pause_event or asyncio.Event()
        self._pause_event.set()

    def stop(self) -> None:
        """Signal the worker to stop at the next opportunity."""
        self._stop_flag = True

    def pause(self) -> None:
        """Freeze the crawler without losing queue state."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume the crawler from where it paused."""
        self._pause_event.set()

    def run(self) -> None:
        """Entry point for the background thread."""
        asyncio.run(self._crawl())
        self.crawl_finished.emit()

    async def _crawl(self) -> None:
        """
        Async crawl loop.

        Emits email_found for each scraped match and
        candidate_found for each pattern-generated address.
        """
        seen: set[str] = set()
        crawler = Crawler(
            seeds=self._seeds,
            phase2_enabled=self._phase2_enabled,
            phase1_timeout=self._phase1_timeout,
            max_pages=self._max_pages,
            respect_robots=self._respect_robots,
            concurrency=self._concurrency,
            pause_event=self._pause_event, # type: ignore
        )

        pages = 0
        async for url, html in crawler.crawl():
            if self._stop_flag:
                break

            self.debug_message.emit(f"[crawl] {url}")
            pages += 1
            self.page_crawled.emit(pages)

            # Scraped emails
            for record in extract_emails(html, url):
                email = record['email']
                if self._target and not email.endswith(self._target):
                    continue
                if email not in seen:
                    seen.add(email)
                    self.email_found.emit(email, url)

            # Pattern-generated candidates
            if self._pattern and self._target:
                for candidate in generate_candidates(html, self._pattern, self._target):
                    if candidate not in seen:
                        seen.add(candidate)
                        self.candidate_found.emit(candidate, url)

            # Polite delay — keeps CPU and network load low
            await asyncio.sleep(self._request_delay)