"""
Unit tests for the Qt-free orchestration pipeline.

All offline: the crawler is replaced with a fake yielding canned HTML.
Run with: pytest tests/test_pipeline.py -v
"""

import asyncio

from app.core import pipeline
from app.core.verifier import VerificationResult, VStatus


class _FakeCrawler:
    """Stand-in for Crawler that yields canned (url, html) pairs."""

    pages: list[tuple[str, str]] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    async def crawl(self):
        for url, html in self.pages:
            yield url, html


def _with_pages(monkeypatch, pages: list[tuple[str, str]]) -> None:
    """Patch pipeline.Crawler to yield the given pages."""
    monkeypatch.setattr(
        pipeline, "Crawler", type("_Patched", (_FakeCrawler,), {"pages": pages})
    )


async def _drain(agen) -> list:
    """Collect an async generator into a list."""
    return [item async for item in agen]


def test_crawl_and_extract_deduplicates_across_pages(monkeypatch) -> None:
    """The same address on two pages is yielded once."""
    html = '<a href="mailto:contacto@nunoa.cl">contacto</a>'
    _with_pages(monkeypatch, [("http://a.cl", html), ("http://b.cl", html)])

    found = asyncio.run(_drain(
        pipeline.crawl_and_extract(["http://a.cl"], request_delay=0)
    ))

    assert [d.email for d in found] == ["contacto@nunoa.cl"]
    assert found[0].source_url == "http://a.cl"
    assert found[0].generated is False


def test_crawl_and_extract_filters_by_target_domain(monkeypatch) -> None:
    """Addresses outside the target domain are dropped."""
    html = (
        '<a href="mailto:a@nunoa.cl">a</a>'
        '<a href="mailto:b@otracosa.cl">b</a>'
    )
    _with_pages(monkeypatch, [("http://a.cl", html)])

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"], target_domain="@nunoa.cl", request_delay=0
    )))

    assert [d.email for d in found] == ["a@nunoa.cl"]


def test_crawl_and_extract_marks_generated_candidates(monkeypatch) -> None:
    """Pattern-generated addresses are flagged generated=True."""
    _with_pages(monkeypatch, [("http://a.cl", "<p>Felipe Carvajal</p>")])

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"],
        target_domain="nunoa.cl",
        pattern="{first}.{last}",
        request_delay=0,
    )))

    assert [d.email for d in found] == ["felipe.carvajal@nunoa.cl"]
    assert found[0].generated is True


def test_crawl_and_extract_reports_pages(monkeypatch) -> None:
    """on_page fires once per page with a running count."""
    _with_pages(monkeypatch, [("http://a.cl", ""), ("http://b.cl", "")])
    seen: list[tuple[str, int]] = []

    asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"], request_delay=0, on_page=lambda u, n: seen.append((u, n))
    )))

    assert seen == [("http://a.cl", 1), ("http://b.cl", 2)]


def test_crawl_and_extract_honours_should_stop(monkeypatch) -> None:
    """should_stop halts the crawl even on pages yielding no addresses."""
    _with_pages(monkeypatch, [("http://a.cl", ""), ("http://b.cl", "")])
    seen: list[tuple[str, int]] = []

    asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"],
        request_delay=0,
        on_page=lambda u, n: seen.append((u, n)),
        should_stop=lambda: True,
    )))

    assert seen == []


def test_verify_all_maps_status_to_string(monkeypatch) -> None:
    """VStatus is converted to the record dict the GUI and exporter expect."""
    monkeypatch.setattr(
        pipeline,
        "verify",
        lambda email, **kw: VerificationResult(email=email, status=VStatus.VALID),
    )

    records = list(pipeline.verify_all([("a@x.cl", "http://x.cl")]))

    assert records == [{
        "email": "a@x.cl",
        "source": "http://x.cl",
        "status": "valid",
        "error": "",
    }]


def test_verify_all_passes_smtp_flag_through(monkeypatch) -> None:
    """smtp_enabled reaches verify() unchanged."""
    captured: dict = {}

    def _fake(email, **kwargs):
        captured.update(kwargs)
        return VerificationResult(email=email, status=VStatus.UNKNOWN)

    monkeypatch.setattr(pipeline, "verify", _fake)
    list(pipeline.verify_all([("a@x.cl", "")], smtp_enabled=False))

    assert captured["smtp_enabled"] is False
