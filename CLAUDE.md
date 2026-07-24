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

# Tests
pytest                            # full suite
pytest -m "not smtp"              # skip tests needing a live internet SMTP connection
pytest tests/test_extractor.py -v # single file
pytest tests/test_verifier.py::test_no_smtp_returns_unknown -v  # single test
```

Packaging (not part of normal dev loop): PyInstaller builds `dist/RadarCL.exe` (no
`.spec` file is committed — generate one with `pyinstaller` before building); the Inno
Setup script `RadarCL.iss` then wraps that exe into `installer/RadarCL-v1.0-Setup.exe`.

## Language

**All user-facing text is always in Spanish** — README, GitHub repo
description, in-app GUI strings/labels (`app/ui/`), and status/error
messages shown to the user. This is a standing rule, not per-file
discretion. Developer-facing text (code, comments, docstrings, commit
messages, this file, ADRs) stays in English. GitHub topics are exempt —
they're fixed platform taxonomy slugs (e.g. `osint`, `chile`), not
translatable prose.

## Architecture

**Strict layering — `app/core/` has zero Qt imports.** All scraping/verification logic
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
- `app/core/exporter.py` — writes only VALID emails to CSV, auto-exported to
  `~/Desktop/RadarCL-YYYY-MM-DD.csv` after verification finishes.

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
