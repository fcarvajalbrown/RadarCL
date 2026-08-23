# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Where this left off — read first (2026-08-23)

**ADR-0024 was measured against real sites, and it works.** Three scans on
2026-08-23, all `--max-seeds 10 --max-pages 40 --no-smtp`, high tier:

| Target | Pages read | Blocked | Kept | Off-target |
|---|---|---|---|---|
| `gecamin.com` | 40, cap reached | 1 | **4** at `@gecamin.com` | 0 |
| `nunoa.cl` | 40, cap reached | 1 | 22 | 2, and reported |
| `bhp.com` | 17 | 4 | 0 | 0 |

Gecamin is the ADR-0024 result: before it, a `.com` target could only return
zero, because no pattern in the extractor could match the address. Also settled,
since ADR-0024 said nobody had checked: **`gecamin.cl` exists**, MX
`gecamin-cl.mail.protection.outlook.com`, same Microsoft 365 tenant as the
`.com`. Nuñoa's zero from the original complaint **did not reproduce** and there
is no log of that run, so nothing here explains it.

**`bhp.com` does not refuse the crawler outright, which is what ADR-0018
recorded.** Seeds 1-3 are `www.bhp.com`, `bhp.com`, `xplor.bhp.com` and none of
them appears in the crawl log. `www.bhp.com` answers **403 from AkamaiGHost**,
`_fetch` swallows it, `on_blocked` never fires, and the crawl spends its whole
budget on the SAP dev and QA subdomains Certificate Transparency happened to
list. That is defect 4 caught in the act.

**`detect_wall` fires but names no vendor** on the four `mobile-*.bhp.com` URLs:
200, a 927-byte JavaScript-only shell, `server: cloudflare` but no
`cf-mitigated` header and no body signature, so `_wall_vendor` returns `''` and
the summary line carries no parentheses. Correctly classed as unreadable; it is
not actually an anti-bot challenge, which the Spanish wording implies.

**The crawl-depth conversation happened.** Felipe decided
[ADR-0025](docs/adr/0025-concurrency-is-real-and-the-user-sets-it.md): the
serial crawl is fixed, tier defaults 2/3/6 stay, **page caps stay untouched
until a parallel crawl has been measured**, and the GUI got a concurrency
spinbox beside the tier badge. Same three domains after: gecamin 30s → 15s,
nunoa 78s → 27s, identical results. Both totals include seed discovery and DNS
verification, which did not change.

Still true and still his to decide: 20 seeds, link depth fixed at 3 (no caller
passes `max_depth`, no setting anywhere), page cap 1000/2000/5000 by tier. The
`Rápida / Profunda` selector in the GUI is *verification* depth (it flips SMTP
on and off); there is no deep-crawl mode.

**Three audit defects remain unfixed**, each needing its own ADR: the unbounded
subdomain probe in `_verify_subdomains`, `max_seeds` truncation discarding the
scored contact pages before they are ever seeded, and fetch failures being
swallowed with no `on_blocked` for a non-2xx. The last has evidence behind it
now (the 403 above) and is the one to take first.

**Never name an organisation as this project's owner, sponsor or audience.** See
"What this is" below. It has come back three times.

**Known, deliberate, and not to be rediscovered as bugs:**

- **`detect_entity_type` misclassifies.** It called `huachipatofc.cl` (a
  football club), `editorialusach.cl` (a publisher) and `supereduc.cl` (the
  schools regulator) universities, by substring-matching `uc`, `usach` and
  `educ`. Recorded in
  [docs/research/pgp-keyserver-yield.md](docs/research/pgp-keyserver-yield.md)
  and left unfixed on purpose: it changes which seeds every scan produces, so
  it needs its own change and its own ADR.
- **Honeypot prevalence on `.cl` was never measured.** Felipe decided the
  demonstrated defect was enough. So nobody knows how often Chilean sites
  actually plant traps — see ADR-0021, which says so rather than implying a
  number exists.
- **Bot-wall prevalence on `.cl` was never measured either.** RadarCL now
  reports a wall honestly; getting *through* one is undecided and gated on
  that measurement, because it needs a headless browser and that is a real
  per-install cost against ADR-0008 and ADR-0005. ADR-0023 deliberately
  pre-registers no threshold, since setting one before knowing what is being
  decided is the invention ADR-0022 refused. The measurement gets its own ADR.
- **The session store is write-only.** `load_session` and `list_sessions` have
  no callers anywhere. `evidence` and `generated` are deliberately *not*
  persisted: ADR-0006 treats session data as sensitive, and adding per-address
  fields nothing can display would increase exposure for nothing. That gap
  stays open, blocked on there being a reader.
- **The GUI two-phase write is correct, not a bug.** `save_email` is called at
  discovery with status defaulting to `unknown`, then `update_email_status`
  fills it in after verification. `tests/test_session.py` pins the sequence.

**Next roadmap items:** v0.70 infers the email pattern instead of asking the
user for it; v0.80 harvests PDFs and documents. Both are measured before they
are built.

## What this is

RadarCL is a Windows desktop app (PySide6/Qt6) by Felipe Carvajal Brown that discovers
and verifies `.cl` email addresses from Chilean websites. It crawls sites starting from
auto-discovered seed URLs, extracts/generates candidate emails, and runs them through a
multi-stage verifier.

**The credit is personal, never institutional.** No organisation is named as
owner, sponsor or audience of this project, anywhere. This was fixed once in
commit `d672c34` across the app window title, the Qt organization name, the
installer publisher and the README, and it came back in `f8db520` through the
PRD, and again on 2026-08-22 in an ADR draft that had read it here and taken it
as current fact. If you are about to write who RadarCL is for, the answer is
Felipe, and nothing else is to be inferred from an older document.

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
| `README.md` | the `versión` badge URL. Nothing else: "Historial de versiones" is a link to CHANGELOG.md, not a list, so there is no entry to add there |

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

**Check the exe is not stale before packaging it.** ISCC only re-wraps
whatever `dist\RadarCL.exe` already is; it never runs PyInstaller. Run
ISCC alone after editing code and you get a setup with a fresh timestamp
and a stale binary inside, and neither command fails. This happened
during v0.4.0: a setup built at 21:30 wrapped a 19:42 exe that still
contained a stage removed at 20:51. In PowerShell, between the two
commands above:

```powershell
$exe = Get-Item dist\RadarCL.exe
$src = Get-ChildItem app -Recurse -File -Include *.py |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($src.LastWriteTime -gt $exe.LastWriteTime) {
  Write-Output "STALE: $($src.Name) is newer than dist\RadarCL.exe"
} else { Write-Output "OK" }
```

`-Include *.py` matters: without it `__pycache__` churn from a test run
reports STALE every time, and a guard that cries wolf gets ignored. Both
branches were verified on the v0.4.0 build.

**Do not grep the exe for a string literal. It does not work, and it
reads as if it does.** Until v0.5.0 this section recommended grepping for
a string that should be gone, citing `grep -c "subdere.gov.cl"` returning
0 on the v0.4.0 build. Tested properly on the v0.5.0 build, strings that
are unquestionably in the shipped code return 0 as well:

```
sessions.db        0
mailto:            0
Rastreo completo   0
```

In a `--onefile` build the bytecode is LZMA-compressed inside the archive,
so no literal from `app/` is greppable. The v0.4.0 check passed for the
wrong reason and would have passed with the stage still in.

What is greppable is the archive's table of contents, which holds **module
names** uncompressed. That is a real check:

```bash
grep -c "provenance" dist\RadarCL.exe    # 1 on the v0.5.0 build
```

It confirms a module is bundled. It cannot confirm a string was removed,
so a release that deletes something needs a different check, or none, but
not a grep that always says yes.

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
  URLs via a cascading pipeline: certificate-transparency subdomains → DNS/HTTP
  liveness check → entity-aware semantic link scoring → optional DuckDuckGo search.
  Each stage fails silently so the next still runs. Entity type (municipality/government/
  university/company) is auto-detected and changes which link-scoring table and which
  DuckDuckGo queries are used — municipality detection first checks the hardcoded
  `_CL_MUNICIPALITIES` set (Lupa Municipal 2026 list) before falling back to keyword match.
  Stage 1 is itself a chain: `_ct_subdomains` tries crt.sh then CertSpotter and stops at
  the first *non-empty* result, since a source answering with no records has answered.
  Only an all-sources failure raises `CTUnavailable`, which `discover_seeds` catches
  ([ADR-0011](docs/adr/0011-ct-fallback-and-source-hygiene.md)) — the fallback lives
  inside stage 1 and is not a new stage. **A curated-source stage was removed in v0.4.0
  and should not be reintroduced without measuring it first**: it seeded a hardcoded list
  of Chilean institutional sites, and its link scoring never fired because no
  institutional homepage links to a target by URL. Crawling all twelve sources for 451
  pages harvested 97 `.cl` addresses and none belonging to any of eight targets; on seven
  of those eight, `max_seeds` truncation discarded its seeds entirely, and on the eighth
  they took 60% of the crawl budget for nothing
  ([ADR-0013](docs/adr/0013-curated-source-stage-removed-after-measurement.md)). "More
  sources" is intuitive and was wrong here, so measure recovered addresses per page
  spent before adding one.
- `app/core/scope.py` — **the one rule for what is in scope**
  ([ADR-0024](docs/adr/0024-scope-follows-the-target-domain.md)). Name a target
  domain and an address at that domain is in scope whatever its TLD; name none
  and scope is `.cl`. This replaced five independent hardcoded `.cl` checks that
  each produced silence rather than a refusal, which is why `scan bhp.com`
  crawled for minutes and reported zero. **Do not add a sixth**: extractor,
  verifier, crawler, pipeline and seed_discoverer all read this module. `covers`
  matches the domain and its subdomains but not a lookalike — `notnunoa.cl` is
  not `nunoa.cl`, and the filter used to be a bare `endswith` that said it was.
- `app/core/crawler.py` — async `httpx` crawler. Phase 1 follows links on `.cl`
  hosts and on the target domain (`scope.host_in_scope`); Phase 2 (optional,
  activated after `phase1_timeout`) follows anything. `.cl` stays crawlable even
  with a `.com` target, so a Chilean page linked from it is still read; narrowing
  results to the target is `pipeline`'s job, not the crawler's. Supports
  pause/resume via an `asyncio.Event` shared with the worker.
  **`concurrency` is real since
  [ADR-0025](docs/adr/0025-concurrency-is-real-and-the-user-sets-it.md)** —
  `crawl()` keeps a frontier deque and a set of in-flight tasks, dispatching up
  to `concurrency` fetches and yielding each page as it arrives, so page order
  is no longer the frontier's. Until then it awaited each `_fetch` inline and
  the semaphore never had a second waiter, which is why every crawl was serial
  whatever the hardware profile declared. The page cap is checked before
  dispatch, so a cap of 2 with 6 seeds costs 2 requests. Pause holds dispatch
  and lets in-flight requests finish; closing the generator, which is what
  `should_stop` does one layer up, cancels what is outstanding.
- `app/core/extractor.py` — pulls in-scope emails from a page's HTML: `mailto:`
  links, plain-text regex, and de-obfuscation of patterns like
  `user [at] domain.cl`. Takes a `target` and matches `.cl` alongside it, so
  `pipeline` can see and report the addresses it is about to discard rather than
  folding them into a zero.
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
- `app/core/verifier.py` — **`_SYNTAX_RE` judges syntax, not scope.** It used to
  end in `\.cl$`, so a well-formed `.com` address was reported as
  `Invalid email format` — a scope refusal wearing a syntax error's reason, and
  the defect ADR-0018 recorded as why `.com` never worked end to end. Do not put
  a TLD back in it. Sequential pipeline per email: syntax regex → DNS MX lookup →
  raw SMTP `RCPT TO` handshake (no email actually sent). Three stages, not four: a
  fourth third-party API stage was a placeholder no interface exposed and was removed
  rather than built, since the commercial APIs are 70-85% accurate on catch-all domains
  ([ADR-0015](docs/adr/0015-no-third-party-verification-api.md)).
  Returns a `VerificationResult` with a `VStatus` of VALID/CATCH_ALL/UNKNOWN/INVALID;
  SMTP failures/timeouts land in UNKNOWN rather than INVALID since many servers block
  verification probes. A 250 from a server that also accepts invented addresses is
  CATCH_ALL, not VALID, and is kept out of the mailable CSV
  ([ADR-0016](docs/adr/0016-catch-all-domains-are-not-valid.md)).
  **A 5xx is INVALID only when its RFC 3463 subject is about the address** (1 addressing,
  2 mailbox); policy, routing, protocol and mail-system failures are facts about the
  sender or the path, so they are UNKNOWN, and `X.2.2` (mailbox full) proves the mailbox
  exists ([ADR-0017](docs/adr/0017-a-reply-is-evidence-only-about-its-subject.md)).
  The probe announces this host's own FQDN, overridable with `RADARCL_HELO`, and the
  null sender. It used to announce `verify.cl`, a domain the project does not own.
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
