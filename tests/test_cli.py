"""
Unit tests for the headless CLI.

All offline: no network, no subprocess. Run with: pytest tests/test_cli.py -v
"""

import io
import json
import sys

import pytest

from app import cli


def test_importing_cli_does_not_load_qt() -> None:
    """
    The CLI must be usable without the GUI stack installed.

    Guards the layering rule in CLAUDE.md: app/core/ and app/cli.py have
    zero Qt imports.
    """
    for module in list(sys.modules):
        assert not module.startswith("PySide6"), (
            f"{module} was imported by app.cli or its dependencies"
        )


def test_discover_parses_defaults() -> None:
    """discover defaults: 20 seeds, DuckDuckGo on, not quiet."""
    args = cli.build_parser().parse_args(["discover", "nunoa.cl"])
    assert args.command == "discover"
    assert args.domain == "nunoa.cl"
    assert args.max_seeds == 20
    assert args.no_duckduckgo is False
    assert args.quiet is False


def test_discover_parses_overrides() -> None:
    """Explicit flags override the defaults."""
    args = cli.build_parser().parse_args(
        ["discover", "nunoa.cl", "--max-seeds", "5", "--no-duckduckgo", "--quiet"]
    )
    assert args.max_seeds == 5
    assert args.no_duckduckgo is True
    assert args.quiet is True


def test_missing_subcommand_is_a_usage_error() -> None:
    """argparse exits with code 2 when no subcommand is given."""
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args([])
    assert exc.value.code == 2


def test_format_row_is_tab_separated() -> None:
    """stdout rows are email, status, source separated by tabs."""
    assert cli.format_row("a@x.cl", "valid", "http://x.cl") == (
        "a@x.cl\tvalid\thttp://x.cl"
    )


def test_read_seeds_skips_blanks_and_comments(tmp_path) -> None:
    """Seed files ignore blank lines and '#' comments."""
    path = tmp_path / "seeds.txt"
    path.write_text(
        "http://a.cl\n\n# un comentario\nhttp://b.cl\n", encoding="utf-8"
    )
    assert cli.read_seeds(str(path)) == ["http://a.cl", "http://b.cl"]


def test_read_email_list_accepts_bare_addresses(tmp_path) -> None:
    """A plain list of addresses yields empty source URLs."""
    path = tmp_path / "emails.txt"
    path.write_text("a@x.cl\n\n# nota\nb@y.cl\n", encoding="utf-8")
    assert cli.read_email_list(str(path)) == [("a@x.cl", ""), ("b@y.cl", "")]


def test_read_email_list_accepts_scan_tsv(tmp_path) -> None:
    """scan's own TSV round-trips back in, keeping the source URL."""
    path = tmp_path / "out.tsv"
    path.write_text("a@x.cl\tvalid\thttp://x.cl\n", encoding="utf-8")
    assert cli.read_email_list(str(path)) == [("a@x.cl", "http://x.cl")]


def test_read_email_list_reads_stdin(monkeypatch) -> None:
    """'-' reads addresses from stdin."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("a@x.cl\nb@y.cl\n"))
    assert cli.read_email_list("-") == [("a@x.cl", ""), ("b@y.cl", "")]


def test_log_writes_to_stderr_not_stdout(capsys) -> None:
    """Progress messages must never pollute the data stream."""
    cli.log("Buscando semillas...", quiet=False)
    captured = capsys.readouterr()
    assert captured.err.strip() == "Buscando semillas..."
    assert captured.out == ""


def test_log_is_silent_when_quiet(capsys) -> None:
    """--quiet suppresses stderr progress output."""
    cli.log("Buscando semillas...", quiet=True)
    assert capsys.readouterr().err == ""


def test_discover_prints_seeds_to_stdout(monkeypatch, capsys) -> None:
    """discover writes one seed URL per line to stdout."""
    async def _fake_discover(domain, use_duckduckgo=True, max_seeds=20):
        return ["http://a.cl", "http://b.cl"]

    monkeypatch.setattr(cli, "discover_seeds", _fake_discover)

    assert cli.main(["discover", "nunoa.cl"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "http://a.cl\nhttp://b.cl\n"
    assert "2 semillas encontradas." in captured.err


def test_verify_parses_defaults() -> None:
    """verify defaults: SMTP on, no output file, session writes on."""
    args = cli.build_parser().parse_args(["verify", "--input", "e.txt"])
    assert args.command == "verify"
    assert args.input == "e.txt"
    assert args.no_smtp is False
    assert args.output is None
    assert args.no_session is False


def test_verify_requires_input() -> None:
    """--input is mandatory for verify."""
    with pytest.raises(SystemExit) as exc:
        cli.build_parser().parse_args(["verify"])
    assert exc.value.code == 2


def test_verify_prints_tsv_rows(monkeypatch, capsys, tmp_path) -> None:
    """verify writes tab-separated rows to stdout and a summary to stderr."""
    path = tmp_path / "emails.txt"
    path.write_text("a@x.cl\nb@y.cl\n", encoding="utf-8")

    def _fake_verify_all(emails, **kwargs):
        for email, source in emails:
            yield {
                "email": email,
                "source": source,
                "status": "valid",
                "error": "",
            }

    monkeypatch.setattr(cli, "verify_all", _fake_verify_all)
    monkeypatch.setattr(cli, "new_session", lambda *a, **k: 1)
    monkeypatch.setattr(cli, "save_email", lambda *a, **k: None)

    assert cli.main(["verify", "--input", str(path)]) == 0

    captured = capsys.readouterr()
    assert captured.out == "a@x.cl\tvalid\t\nb@y.cl\tvalid\t\n"
    assert "2 validos" in captured.err


def test_verify_no_session_skips_persistence(monkeypatch, tmp_path) -> None:
    """--no-session writes nothing to the SQLite store."""
    path = tmp_path / "emails.txt"
    path.write_text("a@x.cl\n", encoding="utf-8")

    def _boom(*args, **kwargs):
        raise AssertionError("session store must not be touched")

    monkeypatch.setattr(cli, "new_session", _boom)
    monkeypatch.setattr(cli, "save_email", _boom)
    monkeypatch.setattr(
        cli,
        "verify_all",
        lambda emails, **kw: iter([
            {"email": "a@x.cl", "source": "", "status": "unknown", "error": ""}
        ]),
    )

    assert cli.main(["verify", "--input", str(path), "--no-session"]) == 0


def test_verify_writes_csv_when_output_given(monkeypatch, tmp_path) -> None:
    """--output writes valid results through the existing CSV exporter."""
    path = tmp_path / "emails.txt"
    path.write_text("a@x.cl\n", encoding="utf-8")
    out = tmp_path / "out.csv"

    monkeypatch.setattr(
        cli,
        "verify_all",
        lambda emails, **kw: iter([
            {"email": "a@x.cl", "source": "http://x.cl",
             "status": "valid", "error": ""}
        ]),
    )

    assert cli.main([
        "verify", "--input", str(path), "--output", str(out), "--no-session"
    ]) == 0
    assert "a@x.cl" in out.read_text(encoding="utf-8")


def _one_of_each(monkeypatch) -> None:
    """Stub verify_all with one result per status."""
    monkeypatch.setattr(
        cli,
        "verify_all",
        lambda emails, **kw: iter([
            {"email": "a@x.cl", "source": "https://x.cl",
             "status": "valid", "error": ""},
            {"email": "b@x.cl", "source": "https://x.cl",
             "status": "unknown", "error": "SMTP RCPT code 450"},
        ]),
    )


def test_verify_infers_json_from_the_extension(monkeypatch, tmp_path) -> None:
    """--output out.json needs no second flag, and keeps every status."""
    path = tmp_path / "emails.txt"
    path.write_text("a@x.cl\nb@x.cl\n", encoding="utf-8")
    out = tmp_path / "out.json"
    _one_of_each(monkeypatch)

    assert cli.main([
        "verify", "--input", str(path), "--output", str(out), "--no-session"
    ]) == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert [r["email"] for r in payload["results"]] == ["a@x.cl", "b@x.cl"]


def test_verify_format_flag_overrides_extension(monkeypatch, tmp_path) -> None:
    """--format html wins over an extension that says otherwise."""
    path = tmp_path / "emails.txt"
    path.write_text("a@x.cl\n", encoding="utf-8")
    out = tmp_path / "raro.txt"
    _one_of_each(monkeypatch)

    assert cli.main([
        "verify", "--input", str(path), "--output", str(out),
        "--format", "html", "--no-session",
    ]) == 0
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_bad_output_extension_fails_before_any_work(
    monkeypatch, tmp_path, capsys
) -> None:
    """An unusable --output must not cost a full verification run first."""
    path = tmp_path / "emails.txt"
    path.write_text("a@x.cl\n", encoding="utf-8")

    def _boom(*args, **kwargs):
        raise AssertionError("verification must not start")

    monkeypatch.setattr(cli, "verify_all", _boom)
    monkeypatch.setattr(cli, "read_email_list", _boom)

    code = cli.main([
        "verify", "--input", str(path), "--output",
        str(tmp_path / "out.txt"), "--no-session",
    ])

    assert code == 2
    assert "formato" in capsys.readouterr().err


def test_scan_parses_defaults() -> None:
    """scan defaults leave tuning to the hardware profile (None = auto)."""
    args = cli.build_parser().parse_args(["scan", "nunoa.cl"])
    assert args.command == "scan"
    assert args.domain == "nunoa.cl"
    assert args.seeds is None
    assert args.pattern == ""
    assert args.max_pages is None
    assert args.concurrency is None
    assert args.delay is None
    assert args.phase2 is False
    assert args.no_smtp is False


def test_scan_parses_overrides() -> None:
    """Explicit tuning flags override the hardware profile."""
    args = cli.build_parser().parse_args([
        "scan", "nunoa.cl",
        "--pattern", "{first}.{last}",
        "--max-pages", "50",
        "--concurrency", "2",
        "--delay", "1.5",
        "--phase2",
        "--phase1-timeout", "30",
    ])
    assert args.pattern == "{first}.{last}"
    assert args.max_pages == 50
    assert args.concurrency == 2
    assert args.delay == 1.5
    assert args.phase2 is True
    assert args.phase1_timeout == 30.0


def test_scan_runs_pipeline_and_prints_results(
    monkeypatch, capsys, tmp_path
) -> None:
    """scan discovers, crawls and verifies, printing TSV rows to stdout."""
    seeds_file = tmp_path / "seeds.txt"
    seeds_file.write_text("http://a.cl\n", encoding="utf-8")

    async def _fake_crawl(seeds, target_domain=None, **kwargs):
        yield cli.Discovery(
            email="contacto@nunoa.cl",
            source_url="http://a.cl",
            generated=False,
            evidence=("lexicon", "phone-cl"),
        )

    seen_evidence: list[tuple] = []

    def _fake_verify(emails, **kw):
        # Mirrors verify_all's real arity: scan passes evidence through,
        # the verify subcommand has none to pass.
        for email, source, *rest in emails:
            seen_evidence.append(rest[0] if rest else None)
            yield {"email": email, "source": source,
                   "status": "valid", "error": ""}

    monkeypatch.setattr(cli, "crawl_and_extract", _fake_crawl)
    monkeypatch.setattr(cli, "verify_all", _fake_verify)

    exit_code = cli.main([
        "scan", "nunoa.cl", "--seeds", str(seeds_file), "--no-session"
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out == "contacto@nunoa.cl\tvalid\thttp://a.cl\n"
    assert "1 validos" in captured.err
    # stdout stays three fields (ADR-0014); evidence reaches the verifier
    # instead, for the JSON and HTML exports to carry.
    assert seen_evidence == [("lexicon", "phone-cl")]


def _fake_crawl_blocking(*pages: tuple[str, str]):
    """Build a crawl_and_extract stub that only ever reports walls."""
    async def _crawl(seeds, target_domain=None, **kwargs):
        for url, vendor in pages:
            kwargs['on_blocked'](url, vendor)
        for _ in ():
            yield

    return _crawl


def test_scan_reports_a_wall_instead_of_zero_addresses(
    monkeypatch, capsys, tmp_path
) -> None:
    """
    Nothing readable is not the same finding as nothing there. Reporting
    the count alone asserts an absence nobody observed (ADR-0023).
    """
    seeds_file = tmp_path / "seeds.txt"
    seeds_file.write_text("https://www.aprimin.cl\n", encoding="utf-8")

    monkeypatch.setattr(
        cli, "crawl_and_extract",
        _fake_crawl_blocking(("https://www.aprimin.cl", "SiteGround")),
    )
    monkeypatch.setattr(cli, "verify_all", lambda emails, **kw: iter([]))

    code = cli.main([
        "scan", "aprimin.cl", "--seeds", str(seeds_file), "--no-session"
    ])

    err = capsys.readouterr().err
    assert "SiteGround" in err
    assert "Ninguna pagina se pudo leer" in err
    assert "no significa que el sitio no tenga correos" in err
    assert code == 1


def test_scan_names_no_vendor_when_the_wall_is_unrecognised(
    monkeypatch, capsys, tmp_path
) -> None:
    """An unnamed wall still reports; it just cannot say who served it."""
    seeds_file = tmp_path / "seeds.txt"
    seeds_file.write_text("https://otro.cl\n", encoding="utf-8")

    monkeypatch.setattr(
        cli, "crawl_and_extract", _fake_crawl_blocking(("https://otro.cl", "")),
    )
    monkeypatch.setattr(cli, "verify_all", lambda emails, **kw: iter([]))

    cli.main(["scan", "otro.cl", "--seeds", str(seeds_file), "--no-session"])

    err = capsys.readouterr().err
    assert "Ninguna pagina se pudo leer:" in err
    assert "()" not in err


def test_scan_still_succeeds_when_some_pages_were_readable(
    monkeypatch, capsys, tmp_path
) -> None:
    """
    A partly walled site is not a failed scan. The blocked pages are still
    reported, so the count is read with them in view.
    """
    seeds_file = tmp_path / "seeds.txt"
    seeds_file.write_text("https://mixto.cl\n", encoding="utf-8")

    async def _crawl(seeds, target_domain=None, **kwargs):
        kwargs['on_blocked']("https://mixto.cl/privado", "Cloudflare")
        kwargs['on_page']("https://mixto.cl", 1)
        yield cli.Discovery(
            email="contacto@mixto.cl",
            source_url="https://mixto.cl",
            generated=False,
        )

    monkeypatch.setattr(cli, "crawl_and_extract", _crawl)
    monkeypatch.setattr(
        cli, "verify_all",
        lambda emails, **kw: iter([
            {"email": "contacto@mixto.cl", "source": "https://mixto.cl",
             "status": "valid", "error": ""}
        ]),
    )

    code = cli.main([
        "scan", "mixto.cl", "--seeds", str(seeds_file), "--no-session"
    ])

    err = capsys.readouterr().err
    assert code == 0
    assert "1 pagina" in err
    assert "Cloudflare" in err


def test_scan_fails_when_no_seeds(monkeypatch, capsys) -> None:
    """With no seeds discovered, scan reports an error and exits 1."""
    async def _no_seeds(domain, use_duckduckgo=True, max_seeds=20):
        return []

    monkeypatch.setattr(cli, "discover_seeds", _no_seeds)

    assert cli.main(["scan", "nunoa.cl", "--no-session"]) == 1
    assert "No se encontraron semillas" in capsys.readouterr().err
