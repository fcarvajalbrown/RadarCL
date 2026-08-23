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

from app.core.pipeline import crawl_and_extract


class CrawlerWorker(QThread):
    """
    Runs the crawl + extraction pipeline in a background thread.

    Signals
    -------
    email_found : Signal(str, str, object, bool)
        Emitted for each discovered email: (email_address, source_url,
        evidence, hidden). Evidence is the `Discovery.evidence` tuple,
        carried as `object` because Qt has no tuple-of-str signal type; it
        travels to the exporters and is not displayed (ADR-0014). `hidden`
        says the address was found only in markup a reader cannot see,
        which keeps it out of the CSV.
    candidate_found : Signal(str, str, object, bool)
        Emitted for each pattern-generated candidate: (email, source_url,
        evidence, hidden). A generated candidate is never hidden - it was
        invented, not read off a page - and the argument is present so both
        signals carry one shape.
    debug_message : Signal(str)
        Emitted for crawler debug messages (URLs visited, errors).
    page_blocked : Signal(str, str)
        Emitted as (url, vendor) for each page fetched but unreadable.
        Vendor is '' when the wall is unrecognised. Without this the GUI
        would auto-export an empty CSV to the Desktop and say nothing about
        why it is empty (ADR-0023).
    email_filtered : Signal(str, str)
        Emitted as (email, source_url) for each distinct .cl address read
        off a page and then discarded for not belonging to the target
        domain. Without it a scan that harvested forty addresses on other
        domains hands the user an empty CSV and a count of zero, which
        reads as "the site publishes no correos".
    crawl_finished : Signal()
        Emitted when the crawl completes or is stopped.
    """

    email_found: Signal = Signal(str, str, object, bool)
    candidate_found: Signal = Signal(str, str, object, bool)
    debug_message: Signal = Signal(str)
    page_crawled: Signal = Signal(int)
    page_blocked: Signal = Signal(str, str)
    email_filtered: Signal = Signal(str, str)
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
        Consume the shared pipeline, re-emitting each result as a signal.

        All crawl/extract/generate logic lives in app.core.pipeline; this
        method only bridges it onto the Qt signal layer.
        """
        def on_page(url: str, count: int) -> None:
            self.debug_message.emit(f"[crawl] {url}")
            self.page_crawled.emit(count)

        def on_blocked(url: str, vendor: str) -> None:
            suffix = f" - {vendor}" if vendor else ""
            self.debug_message.emit(f"[bloqueado] {url}{suffix}")
            self.page_blocked.emit(url, vendor)

        def on_filtered(email: str, url: str) -> None:
            self.debug_message.emit(f"[fuera de dominio] {email}")
            self.email_filtered.emit(email, url)

        async for discovery in crawl_and_extract(
            self._seeds,
            target_domain=self._target,
            phase2_enabled=self._phase2_enabled,
            phase1_timeout=self._phase1_timeout,
            max_pages=self._max_pages,
            respect_robots=self._respect_robots,
            pattern=self._pattern,
            request_delay=self._request_delay,
            concurrency=self._concurrency,
            pause_event=self._pause_event,
            on_page=on_page,
            on_blocked=on_blocked,
            on_filtered=on_filtered,
            should_stop=lambda: self._stop_flag,
        ):
            if discovery.generated:
                self.candidate_found.emit(
                    discovery.email, discovery.source_url, discovery.evidence,
                    discovery.hidden,
                )
            else:
                self.email_found.emit(
                    discovery.email, discovery.source_url, discovery.evidence,
                    discovery.hidden,
                )