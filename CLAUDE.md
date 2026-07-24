# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RadarCL is a Windows desktop app (PySide6/Qt6) that discovers and verifies `.cl` email
addresses from Chilean websites, for Instituto Igualdad's Área de Innovación Tecnológica.
It crawls sites starting from auto-discovered seed URLs, extracts/generates candidate
emails, and runs them through a multi-stage verifier.

## Commands

```bash
# Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Run the app
python -m app.main

# Run the CLI (headless, no Qt)
python -m app.cli --help
python -m app.cli discover nunoa.cl
python -m app.cli scan nunoa.cl --pattern "{first}.{last}" --output out.csv
python -m app.cli verify --input emails.txt --no-smtp

# Tests
pytest                            # full suite
pytest -m "not smtp"              # skip tests needing a live internet connection (DNS or SMTP)
pytest tests/test_extractor.py -v # single file
pytest tests/test_verifier.py::test_no_smtp_returns_unknown -v  # single test

# Vendored dependencies (ADR-0008)
python scripts/vendor.py            # rebuild vendor/ + requirements-core.lock
python scripts/vendor.py --check    # verify vendor/ against SHA256SUMS.txt
pip install --no-index --find-links=vendor --require-hashes -r requirements-core.lock
```

**Dependency changes require two steps**: bump the range in
`requirements-core.txt`, then rerun `python scripts/vendor.py` and commit
the regenerated `vendor/`, `SHA256SUMS.txt` and `requirements-core.lock`.
A `vendor/` that disagrees with `requirements-core.txt` is a real failure
mode — `--check` verifies integrity, not currency.

## Releases

**Cut a new installer on every 0.1 version bump** — v0.4, v0.5, v0.6 and
so on up to v1.0. Not on 0.05 increments: those are code milestones, not
distribution events, and rebuilding a 57 MB binary for each one is waste.
v0.3.5 got an installer anyway because Felipe asked for one directly; that
was an explicit exception, not the rule.

Never commit the build output. `dist/` and `installer/` are gitignored.
Committing them once pushed this repository past 110 MB and had to be
undone by rewriting history — the artifacts ship as binaries attached to a
GitHub Release instead.

**1. Bump the version in all four places.** They drift silently otherwise,
and Windows uses `AppVersion` to decide whether an install is an upgrade:

| File | What to change |
|---|---|
| `pyproject.toml` | `version = "0.4.0"` |
| `app/__init__.py` | `__version__ = "0.4.0"` — this is what the CLI's `--version`, the JSON export and the HTML report all stamp |
| `RadarCL.iss` | `#define AppVersion "0.4.0"`; `OutputBaseFilename` derives from it |
| `README.md` | the `versión` badge URL, plus a new entry at the top of "Historial de versiones" |

**2. Verify before building.** A broken build is worse than no release:

```bash
venv\Scripts\python.exe -m pytest -m "not smtp"
venv\Scripts\python.exe scripts/vendor.py --check
```

**3. Build.** No `.spec` is committed (it is gitignored), so generate one:

```bash
venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed ^
  --icon assets\icon.ico --add-data "assets;assets" ^
  --name RadarCL app\main.py
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" RadarCL.iss
```

Output: `installer\RadarCL-v<version>-Setup.exe`. Run it once before
publishing — PyInstaller builds fail at runtime, not at build time, and
the frozen-asset path resolution (`sys._MEIPASS`) is exactly the kind of
thing that only breaks in the packaged exe.

**4. Publish.** Tag and Release, with the installer attached:

```bash
python scripts/release_notes.py 0.4.0 > notes.md
git tag -a v0.4.0 -m "RadarCL v0.4.0"
git push origin v0.4.0
gh release create v0.4.0 "installer\RadarCL-v0.4.0-Setup.exe" ^
  --title "RadarCL v0.4.0" --notes-file notes.md
```

**Generate the notes with that script, never by pasting.** GitHub renders
a release body with hard line breaks on, so CHANGELOG.md's 72-column
wrapping survives into the page and produces a ragged half-width column.
The script unwraps the published copy and leaves the file alone.

Publishing is outward-facing and effectively irreversible, so ask Felipe
before creating the Release unless he asked for it in that same turn.

**Release notes have a mandatory template and process** — invoke the
`voz-de-felipe` skill, then run the humanizer pass, then fill the
template. Do not improvise them and do not paste a commit log. The whole
thing lives in [docs/release-notes.md](docs/release-notes.md); read it
before writing a single line of a release.

Antivirus false positives on the PyInstaller exe are a known, unresolved
issue — see `docs/research/oss-tooling.md` and the "Beyond v1.0" section of
[ROADMAP.md](ROADMAP.md).

## Language

**All user-facing text is always in Spanish** — README, GitHub repo
description, in-app GUI strings/labels (`app/ui/`), and status/error
messages shown to the user. This is a standing rule, not per-file
discretion. Developer-facing text (code, comments, docstrings, commit
messages, this file, ADRs) stays in English. GitHub topics are exempt —
they're fixed platform taxonomy slugs (e.g. `osint`, `chile`), not
translatable prose.

## Decisions (ADR)

Design decisions live in `docs/adr/`, indexed by `docs/adr/README.md`.

**Never write an ADR without Felipe's input first — hard rule.** He is the
`Deciders:` line, so an ADR drafted from assumptions is a fabricated record
of his reasoning. Bring him the choice, the real alternatives and a
recommendation through the interactive option UI, then write only what he
picked. Approving a feature is not approving an ADR's contents.

An Accepted ADR is immutable: a changed decision gets a new, next-numbered
ADR, and the only edit ever made to the old one is its Status line.

## Architecture

**Strict layering — `app/core/` and `app/cli.py` have zero Qt imports.**
This is enforced by `tests/test_cli.py::test_importing_cli_does_not_load_qt`,
not just by convention. All scraping/verification logic
lives there as plain async functions and dataclasses, independently testable and reusable
outside the GUI. `app/workers/` contains `QThread` subclasses that are the *only* place
Qt and `core` logic meet — each wraps a `core` async routine and re-emits its results as
Qt signals for the GUI thread. `app/ui/` consumes only worker signals, never calls
`core` directly. Preserve this separation when adding features.

- `app/core/seed_discoverer.py` — turns a bare domain (e.g. `nunoa.cl`) into 10-20 seed
  URLs via a cascading pipeline: crt.sh certificate-transparency subdomains → DNS/HTTP
  liveness check → entity-aware semantic link scoring → hardcoded high-value Chilean
  sources (transparencia.cl, munitel.cl, etc.) → optional DuckDuckGo search. Each stage
  fails silently so the next still runs. Entity type (municipality/government/
  university/company) is auto-detected and changes which link-scoring table and known
  sources are used — municipality detection first checks the hardcoded
  `_CL_MUNICIPALITIES` set (Lupa Municipal 2026 list) before falling back to keyword match.
- `app/core/crawler.py` — async `httpx` crawler. Phase 1 restricts link-following to
  `.cl` domains; Phase 2 (optional, activated after `phase1_timeout`) follows external
  links too, but the email filter (`is_cl_domain`) always stays `.cl`-only regardless of
  phase. Supports pause/resume via an `asyncio.Event` shared with the worker.
- `app/core/extractor.py` — pulls `.cl` emails from a page's HTML: `mailto:` links,
  plain-text regex, and de-obfuscation of patterns like `user [at] domain.cl`.
- `app/core/pattern_generator.py` — for domains where emails aren't published directly,
  harvests likely person names (`Firstname Lastname` capitalisation heuristic, with a
  Chilean first-name set to resolve word order) and generates candidate addresses from a
  template (`{first}.{last}`, `{f}{last}`, etc.) — see `COMMON_PATTERNS` for presets.
- `app/core/dns_lookup.py` — MX resolution with fallback transports: system
  resolver → public nameservers (`8.8.8.8`, `1.1.1.1`) → DNS-over-HTTPS.
  Raises `DomainNotFound` (definitive, → INVALID) or `MXUnavailable`
  (indeterminate, → UNKNOWN); the distinction is the whole point, since a
  resolver timeout is not evidence an address is dead ([ADR-0009](docs/adr/0009-mx-resolution-failure-is-unknown.md)).
  The DoH leg exists because dnspython uses UDP/53, which some networks
  filter while leaving HTTPS working.
- `app/core/verifier.py` — sequential pipeline per email: syntax regex → DNS MX lookup →
  raw SMTP `RCPT TO` handshake (no email actually sent) → optional API stage (currently
  a placeholder). Returns a `VerificationResult` with a `VStatus` of VALID/UNKNOWN/INVALID;
  SMTP failures/timeouts land in UNKNOWN rather than INVALID since many servers block
  verification probes.
- `app/core/hw_profile.py` — detects RAM/CPU at startup and picks a `low`/`medium`/`high`
  tier (concurrency, request delay, max pages) so the app doesn't overwhelm low-spec
  hardware; the tier badge is surfaced in the control panel UI.
- `app/core/session.py` — SQLite store at `~/.radarcl/sessions.db`; auto-prunes to the
  last 10 sessions on each new session creation.
- `app/core/exporter.py` — CSV, JSON and HTML writers behind one `export()`
  dispatcher. **Contents differ by format, deliberately** ([ADR-0010](docs/adr/0010-export-contents-differ-by-format.md)):
  CSV carries VALID only (the mailable deliverable, still auto-exported to
  `~/Desktop/RadarCL-YYYY-MM-DD.csv` after a GUI verification), while JSON
  and HTML carry every record with its `status` and `error`. Format comes
  from the output extension, overridable with an explicit `fmt`; an
  unrecognised extension raises `ValueError` so the CLI can fail before
  crawling rather than after. The HTML report is self-contained — inline
  CSS, no JavaScript, no external asset — and escapes every cell, since it
  renders strings harvested from crawled pages.
- `app/core/pipeline.py` — Qt-free orchestration of the two main loops:
  `crawl_and_extract()` (crawl → extract → pattern-generate, deduplicated,
  yielding `Discovery` objects) and `verify_all()` (verify → record dicts).
  Both `app/cli.py` and the `app/workers/` QThreads consume these, so each
  loop has exactly one implementation. `should_stop` is polled per page,
  not per result, so a Stop still lands on pages containing no addresses.
- `app/cli.py` — headless entry point (`python -m app.cli`) with three
  subcommands: `discover`, `scan`, `verify`. stdout carries data only
  (TSV: email, status, source) so it pipes; Spanish progress goes to
  stderr. Never triggers the Desktop auto-export, since
  `exporter.default_export_path()` creates `~/Desktop` — the CLI writes a
  file only on an explicit `--output`, in the format that path's extension
  implies or that `--format` forces. The format is resolved before the
  crawl starts, not after it.

**Signal flow**: `CrawlerWorker`/`VerifierWorker` emit low-level signals (per-email,
per-page, progress) → `ControlPanel` owns worker lifecycle (start/pause/stop/force-quit),
accumulates collected emails, and re-emits its own higher-level signals
(`email_discovered`, `verification_done`, `new_session_started`, etc.) → `MainWindow`
wires those to the terminal feed and results table and has no worker-management logic
of its own.

**Frozen-build asset path**: both `app/main.py` and `app/ui/control_panel.py` resolve the
`assets/` directory via `sys._MEIPASS` when `sys.frozen` (PyInstaller) is set, falling
back to a relative path in dev — replicate this pattern for any new code that loads
bundled assets.
