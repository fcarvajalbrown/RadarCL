"""
Unit tests for the headless CLI.

All offline: no network, no subprocess. Run with: pytest tests/test_cli.py -v
"""

import io
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
