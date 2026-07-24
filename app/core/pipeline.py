"""
Qt-free orchestration of the crawl/extract/generate and verification loops.

Both `app/cli.py` and the QThread workers in `app/workers/` consume these
generators, so there is exactly one implementation of each loop. Nothing in
this module may import Qt — see the layering rule in CLAUDE.md.
"""

import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Iterator

from app.core.crawler import Crawler
from app.core.extractor import extract_emails
from app.core.pattern_generator import generate_candidates
from app.core.verifier import verify, VStatus


# VStatus is an internal enum; consumers (GUI table, CSV exporter, CLI)
# all key off these lowercase strings.
_STATUS_NAMES: dict[VStatus, str] = {
    VStatus.VALID: 'valid',
    VStatus.INVALID: 'invalid',
    VStatus.UNKNOWN: 'unknown',
}


@dataclass
class Discovery:
    """
    One email address found during a crawl.

    Attributes
    ----------
    email : str
        The address, lowercased.
    source_url : str
        Page the address was found on, or the page whose names produced it.
    generated : bool
        True if pattern-generated, False if scraped from the page.
    """
    email: str
    source_url: str
    generated: bool


async def crawl_and_extract(
    seeds: list[str],
    target_domain: str | None = None,
    *,
    phase2_enabled: bool = False,
    phase1_timeout: float | None = None,
    max_pages: int = 2000,
    respect_robots: bool = False,
    pattern: str = "",
    request_delay: float = 0.5,
    concurrency: int = 3,
    pause_event: asyncio.Event | None = None,
    on_page: Callable[[str, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> AsyncGenerator[Discovery, None]:
    """
    Crawl the seeds and yield each newly discovered email address.

    Parameters
    ----------
    seeds : list[str]
        Starting URLs.
    target_domain : str | None
        Restrict results to this email domain (with or without a leading
        '@'). None accepts any .cl address the extractor returns.
    pattern : str
        Optional pattern template, e.g. '{first}.{last}'. Requires
        target_domain; ignored without one, since a generated local part
        has no domain to attach to.
    request_delay : float
        Seconds slept after each page, to keep load low on old hardware.
    on_page : Callable[[str, int], None] | None
        Called once per fetched page with (url, running_page_count).
    should_stop : Callable[[], bool] | None
        Polled once per page. Returning True ends the crawl. This is
        page-granular on purpose: a consumer that could only stop on a
        yielded Discovery would keep crawling through pages that contain
        no addresses.

    Yields
    ------
    Discovery
        Deduplicated across the whole crawl, scraped addresses first per
        page, then pattern-generated candidates.
    """
    target = target_domain.lower().lstrip('@') if target_domain else None
    seen: set[str] = set()

    crawler = Crawler(
        seeds=seeds,
        phase2_enabled=phase2_enabled,
        phase1_timeout=phase1_timeout,
        max_pages=max_pages,
        respect_robots=respect_robots,
        concurrency=concurrency,
        pause_event=pause_event,  # type: ignore[arg-type]
    )

    pages = 0
    async for url, html in crawler.crawl():
        if should_stop is not None and should_stop():
            break

        pages += 1
        if on_page is not None:
            on_page(url, pages)

        for record in extract_emails(html, url):
            email = record['email']
            if target and not email.endswith(target):
                continue
            if email not in seen:
                seen.add(email)
                yield Discovery(email=email, source_url=url, generated=False)

        if pattern and target:
            for candidate in generate_candidates(html, pattern, target):
                if candidate not in seen:
                    seen.add(candidate)
                    yield Discovery(
                        email=candidate, source_url=url, generated=True
                    )

        # Polite delay — keeps CPU and network load low.
        await asyncio.sleep(request_delay)


def verify_all(
    emails: list[tuple[str, str]],
    *,
    smtp_enabled: bool = True,
    api_key: str | None = None,
) -> Iterator[dict]:
    """
    Verify (email, source_url) pairs, yielding one record per address.

    Parameters
    ----------
    emails : list[tuple[str, str]]
        (email_address, source_url) pairs.
    smtp_enabled : bool
        If False, skip the SMTP handshake stage.
    api_key : str | None
        Enables the verifier's Stage 4 if provided.

    Yields
    ------
    dict
        Keys: 'email', 'source', 'status', 'error'. 'status' is one of
        'valid', 'invalid', 'unknown'. This is the shape
        `exporter.export_valid()` and the GUI results table consume.
    """
    for email, source in emails:
        result = verify(email, smtp_enabled=smtp_enabled, api_key=api_key)
        yield {
            'email': email,
            'source': source,
            'status': _STATUS_NAMES[result.status],
            'error': result.error,
        }
