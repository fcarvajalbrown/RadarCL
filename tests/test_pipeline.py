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


def test_crawl_and_extract_forwards_blocked_pages(monkeypatch) -> None:
    """
    A wall the crawler hit must reach the caller. Swallowing it here would
    leave the CLI and the GUI reporting an absence nobody observed
    (ADR-0023).
    """
    class _Blocking(_FakeCrawler):
        pages: list[tuple[str, str]] = []

        async def crawl(self):
            self.kwargs['on_blocked']('https://www.aprimin.cl', 'SiteGround')
            for url, html in self.pages:
                yield url, html

    monkeypatch.setattr(pipeline, "Crawler", _Blocking)
    seen: list[tuple[str, str]] = []

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["https://www.aprimin.cl"],
        request_delay=0,
        on_blocked=lambda url, vendor: seen.append((url, vendor)),
    )))

    assert found == []
    assert seen == [('https://www.aprimin.cl', 'SiteGround')]


def test_crawl_and_extract_reports_off_target_addresses(monkeypatch) -> None:
    """
    An address dropped for being on another domain reaches the caller.

    A scan that reads forty addresses and keeps none must not report the
    same bare zero as a scan that read nothing.
    """
    html = (
        '<a href="mailto:a@nunoa.cl">a</a>'
        '<a href="mailto:b@otracosa.cl">b</a>'
        '<a href="mailto:c@tercera.cl">c</a>'
    )
    _with_pages(monkeypatch, [("http://a.cl", html), ("http://b.cl", html)])
    dropped: list[tuple[str, str]] = []

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"],
        target_domain="nunoa.cl",
        request_delay=0,
        on_filtered=lambda email, url: dropped.append((email, url)),
    )))

    assert [d.email for d in found] == ["a@nunoa.cl"]
    assert sorted(dropped) == [
        ("b@otracosa.cl", "http://a.cl"),
        ("c@tercera.cl", "http://a.cl"),
    ]


def test_crawl_and_extract_reports_no_off_target_without_a_target(
    monkeypatch,
) -> None:
    """With no target domain nothing is dropped, so nothing is reported."""
    html = '<a href="mailto:b@otracosa.cl">b</a>'
    _with_pages(monkeypatch, [("http://a.cl", html)])
    dropped: list[tuple[str, str]] = []

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"],
        request_delay=0,
        on_filtered=lambda email, url: dropped.append((email, url)),
    )))

    assert [d.email for d in found] == ["b@otracosa.cl"]
    assert dropped == []


def test_describe_off_target_is_silent_when_nothing_was_dropped() -> None:
    """A clean run grows no caveat."""
    assert pipeline.describe_off_target(0, 5, "nunoa.cl") == ""


def test_describe_off_target_refuses_to_imply_an_empty_site() -> None:
    """
    Zero kept and some dropped is the case the whole change exists for.

    The wording must say the addresses were read and rejected, never that
    the site has none.
    """
    text = pipeline.describe_off_target(40, 0, "nunoa.cl")

    assert "40" in text
    assert "nunoa.cl" in text
    assert "otro dominio" in text


def test_describe_off_target_is_a_footnote_when_something_was_kept() -> None:
    """With results in hand the dropped addresses are an aside, not a verdict."""
    text = pipeline.describe_off_target(3, 7, "nunoa.cl")

    assert "3" in text
    assert "no significa" not in text


def test_describe_off_target_says_one_address_in_the_singular() -> None:
    """'Otras 1 direcciones' is the kind of thing a user notices."""
    assert pipeline.describe_off_target(1, 7, "nunoa.cl").startswith(
        "Otra direccion"
    )
    assert "una direccion" in pipeline.describe_off_target(1, 0, "nunoa.cl")


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


def test_generated_candidates_follow_the_target_domain(monkeypatch) -> None:
    """
    A named non-.cl target generates candidates at that domain (ADR-0024).

    ADR-0018 blocked this because `verifier._SYNTAX_RE` then called every
    such address malformed, so the path produced what it could not verify.
    That was a defect in the verifier, and it is fixed rather than avoided.
    """
    _with_pages(monkeypatch, [("http://a.cl", "<p>Jimmy Nunez</p>")])

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"], target_domain="bhp.com",
        pattern="{first}.{last}", request_delay=0
    )))

    assert [d.email for d in found] == ["jimmy.nunez@bhp.com"]
    assert found[0].generated is True


def test_scraped_addresses_follow_the_target_domain(monkeypatch) -> None:
    """
    A .com address on a page is extracted when the user named that domain.

    The extractor regex ended in `\\.cl\\b`, so this could not be matched
    at all and a bhp.com scan reported zero after minutes of crawling.
    """
    html = (
        '<a href="mailto:sarah.wilson@bhp.com">sarah</a>'
        '<a href="mailto:otro@ajeno.com">otro</a>'
    )
    _with_pages(monkeypatch, [("http://a.cl", html)])

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"], target_domain="bhp.com", request_delay=0
    )))

    assert [d.email for d in found] == ["sarah.wilson@bhp.com"]


def test_default_scope_is_still_cl_only(monkeypatch) -> None:
    """With no target named nothing changes: .cl and nothing else."""
    html = (
        '<a href="mailto:uno@nunoa.cl">uno</a>'
        '<a href="mailto:dos@bhp.com">dos</a>'
    )
    _with_pages(monkeypatch, [("http://a.cl", html)])

    found = asyncio.run(_drain(
        pipeline.crawl_and_extract(["http://a.cl"], request_delay=0)
    ))

    assert [d.email for d in found] == ["uno@nunoa.cl"]


def test_target_domain_does_not_match_a_lookalike(monkeypatch) -> None:
    """
    `notnunoa.cl` is not `nunoa.cl`.

    The filter was a bare `endswith`, which let a stranger's domain answer
    for the target. Consolidating five scope checks into one made the loose
    version untenable, since the same rule decides which hosts to crawl.
    """
    html = (
        '<a href="mailto:uno@nunoa.cl">uno</a>'
        '<a href="mailto:dos@notnunoa.cl">dos</a>'
        '<a href="mailto:tres@correo.nunoa.cl">tres</a>'
    )
    _with_pages(monkeypatch, [("http://a.cl", html)])
    dropped: list[str] = []

    found = asyncio.run(_drain(pipeline.crawl_and_extract(
        ["http://a.cl"],
        target_domain="nunoa.cl",
        request_delay=0,
        on_filtered=lambda email, url: dropped.append(email),
    )))

    assert sorted(d.email for d in found) == [
        "tres@correo.nunoa.cl", "uno@nunoa.cl",
    ]
    assert dropped == ["dos@notnunoa.cl"]


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
