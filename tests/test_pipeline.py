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


_CL_PAGE = (
    '<html lang="es-CL"><body>'
    '<p>RUT 76.086.428-5 - Casilla 150 - Fono 22 818 5000</p>'
    '<a href="mailto:uno@nunoa.cl">uno</a>'
    '<a href="mailto:dos@nunoa.cl">dos</a>'
    '</body></html>'
)


def test_evidence_is_attached_to_every_address_from_a_page(monkeypatch) -> None:
    """Evidence describes the page, so every address on it carries the same."""
    _with_pages(monkeypatch, [("http://a.cl/es-cl", _CL_PAGE)])

    found = asyncio.run(_drain(
        pipeline.crawl_and_extract(["http://a.cl"], request_delay=0)
    ))

    assert len(found) == 2
    assert {d.evidence for d in found} == {
        ('lang-es-cl', 'lexicon', 'path-cl', 'phone-cl', 'rut')
    }


def test_evidence_is_computed_once_per_page(monkeypatch) -> None:
    """Two addresses on one page cost one provenance pass, not two."""
    calls: list[str] = []
    monkeypatch.setattr(
        pipeline, "chile_evidence",
        lambda html, url: calls.append(url) or ('lang-es-cl',)
    )
    _with_pages(monkeypatch, [("http://a.cl", _CL_PAGE)])

    asyncio.run(_drain(
        pipeline.crawl_and_extract(["http://a.cl"], request_delay=0)
    ))

    assert calls == ["http://a.cl"]


def test_evidence_is_not_computed_for_pages_without_addresses(monkeypatch) -> None:
    """Most crawled pages carry no address; they must not pay for a parse."""
    calls: list[str] = []
    monkeypatch.setattr(
        pipeline, "chile_evidence", lambda html, url: calls.append(url) or ()
    )
    _with_pages(monkeypatch, [("http://a.cl", "<p>Sin correos aqui</p>")])

    asyncio.run(_drain(
        pipeline.crawl_and_extract(["http://a.cl"], request_delay=0)
    ))

    assert calls == []


def test_evidence_never_admits_a_non_cl_address(monkeypatch) -> None:
    """
    Evidence annotates; it never widens the filter. A page firing every
    signal still yields no .com address on the scraped path (ADR-0014).
    """
    html = _CL_PAGE + '<a href="mailto:someone@bhp.com">someone</a>'
    _with_pages(monkeypatch, [("http://a.cl/es-cl", html)])

    found = asyncio.run(_drain(
        pipeline.crawl_and_extract(["http://a.cl"], request_delay=0)
    ))

    assert all(d.email.endswith('.cl') for d in found)
    assert found[0].evidence  # the page really did carry evidence


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


def test_generated_candidates_are_held_to_cl_scope(monkeypatch) -> None:
    """
    The generated branch had no filter, so a non-.cl target invented
    foreign addresses the verifier then rejected as "Invalid email
    format" - a path that never worked end to end (ADR-0018).
    """
    _with_pages(monkeypatch, [("http://a.cl", "<p>Jimmy Nunez</p>")])

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"], target_domain="bhp.com",
        pattern="{first}.{last}", request_delay=0
    )))

    assert found == []


def test_generated_candidates_still_work_for_cl(monkeypatch) -> None:
    """The capability is scoped, not removed."""
    _with_pages(monkeypatch, [("http://a.cl", "<p>Jimmy Nunez</p>")])

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"], target_domain="nunoa.cl",
        pattern="{first}.{last}", request_delay=0
    )))

    assert any(d.email.endswith('@nunoa.cl') and d.generated for d in found)


def test_a_guess_is_distinguishable_from_a_harvested_address() -> None:
    """
    A pattern guess and a published address are different claims. An
    export that renders them identically hides that (ADR-0018).
    """
    pairs = [
        ('real@nunoa.cl', 'https://nunoa.cl/contacto', ('lexicon',), False),
        ('inventado@nunoa.cl', 'https://nunoa.cl/equipo', (), True),
    ]
    records = list(pipeline.verify_all(pairs, smtp_enabled=False))

    assert records[0]['generated'] is False
    assert records[1]['generated'] is True


def test_generated_key_absent_when_caller_did_not_say() -> None:
    """The verify subcommand has no provenance to report, so it says none."""
    records = list(pipeline.verify_all(
        [('a@nunoa.cl', '')], smtp_enabled=False
    ))
    assert 'generated' not in records[0]
