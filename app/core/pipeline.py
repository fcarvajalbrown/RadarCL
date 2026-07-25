"""
Qt-free orchestration of the crawl/extract/generate and verification loops.

Both `app/cli.py` and the QThread workers in `app/workers/` consume these
generators, so there is exactly one implementation of each loop. Nothing in
this module may import Qt — see the layering rule in CLAUDE.md.
"""

import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Iterator, Sequence

from app.core.crawler import Crawler
from app.core.extractor import extract_emails
from app.core.pattern_generator import generate_candidates
from app.core.provenance import chile_evidence
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
    evidence : tuple[str, ...]
        Chilean-evidence signals found on `source_url` - see
        `app.core.provenance`. Empty means no evidence was found, not that
        the page is foreign, and it is a statement about the page rather
        than about who owns the domain (ADR-0014).
    """
    email: str
    source_url: str
    generated: bool
    evidence: tuple[str, ...] = ()


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

        Naming a non-`.cl` domain here is the only way a non-`.cl` address
        is ever produced, and only through `pattern` below, since the
        scraped path stays `.cl`-only. RadarCL makes no claim that such an
        address is Chilean; the caller asked for that domain by name, and
        `Discovery.evidence` reports what the page showed (ADR-0014).
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

        # Computed at most once per page, and only if the page yields an
        # address: most crawled pages carry none, and this parses the HTML
        # a second time. `None` is the sentinel because `()` is a real
        # answer meaning "no evidence found".
        page_evidence: tuple[str, ...] | None = None

        for record in extract_emails(html, url):
            email = record['email']
            if target and not email.endswith(target):
                continue
            if email not in seen:
                seen.add(email)
                if page_evidence is None:
                    page_evidence = chile_evidence(html, url)
                yield Discovery(
                    email=email, source_url=url, generated=False,
                    evidence=page_evidence,
                )

        if pattern and target:
            for candidate in generate_candidates(html, pattern, target):
                if candidate not in seen:
                    seen.add(candidate)
                    if page_evidence is None:
                        page_evidence = chile_evidence(html, url)
                    yield Discovery(
                        email=candidate, source_url=url, generated=True,
                        evidence=page_evidence,
                    )

        # Polite delay — keeps CPU and network load low.
        await asyncio.sleep(request_delay)


def verify_all(
    emails: Sequence[tuple],
    *,
    smtp_enabled: bool = True,
) -> Iterator[dict]:
    """
    Verify (email, source_url) pairs, yielding one record per address.

    Parameters
    ----------
    emails : Sequence[tuple]
        Either `(email, source_url)` or `(email, source_url, evidence)`,
        where evidence is a `Discovery.evidence` tuple. Both shapes are
        accepted because the `verify` subcommand reads bare addresses from
        a file and has no page to draw evidence from.
    smtp_enabled : bool
        If False, skip the SMTP handshake stage.

    Yields
    ------
    dict
        Keys: 'email', 'source', 'status', 'error', and 'evidence' only
        when the input carried it. 'status' is one of 'valid', 'invalid',
        'unknown'. This is the shape `exporter.export_valid()` and the GUI
        results table consume.

        The key is omitted rather than set to `[]` when no evidence was
        supplied, because an empty list is a real answer meaning the page
        was checked and showed nothing (ADR-0014). Absent means nobody
        looked, and a consumer must not read the two the same way.
    """
    for email, source, *rest in emails:
        result = verify(email, smtp_enabled=smtp_enabled)
        record = {
            'email': email,
            'source': source,
            'status': _STATUS_NAMES[result.status],
            'error': result.error,
        }
        if rest:
            record['evidence'] = list(rest[0])
        yield record
