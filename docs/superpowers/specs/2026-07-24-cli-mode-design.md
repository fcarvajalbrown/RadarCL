# Design — v0.25 verifier fix + v0.30 core-as-library / CLI mode

**Date:** 2026-07-24
**Status:** Approved (brainstorm)
**Milestones:** ROADMAP v0.25 (verifier item only) and v0.30 (all items)

## Goal

Two things, in this order:

1. Fix `app/core/verifier.py`'s SMTP classification, which contradicts
   ADR-0004, and record the corrected rule as ADR-0007.
2. Add `app/cli.py`, a headless Qt-free entry point, and make `app/core/`
   genuinely usable as a standalone import rather than GUI plumbing that
   happens to have no Qt in it.

Part 1 comes first because the CLI calls the same `verify()` and would
otherwise ship reporting known-wrong statuses.

## Part A — SMTP response classification

### Problem

`app/core/verifier.py` sets `VStatus.INVALID` in three places: syntax
(line 71), MX (line 85), and SMTP (line 101). The first two match ADR-0004.
The third does not:

```python
code, _ = smtp.rcpt(email)
result.smtp_ok = code == 250
result.status = VStatus.VALID if result.smtp_ok else VStatus.INVALID
```

ADR-0004 states that a non-250 response results in `UNKNOWN`, not `INVALID`.
So a greylisting `450`, a rate-limit `421`, and a `252` are all filed as
INVALID today — the exact false-negative-on-real-addresses failure that ADR
was written to prevent. The exception handler immediately below correctly
returns UNKNOWN, so the module's behaviour currently depends on whether a
server refuses politely or drops the connection.

### Decision

Classify by SMTP reply-code class rather than by "is it 250":

| Reply code | Status | Rationale |
|---|---|---|
| `250` | VALID | Recipient accepted. |
| `5xx` | INVALID | Permanent failure per RFC 5321. `550 5.1.1` is defined as "Bad destination mailbox address" and is the canonical non-existent-mailbox response to `RCPT TO`. |
| `4xx` | UNKNOWN | Transient by definition; greylisting returns `450`/`451`, rate-limiting `421`. A retry is expected, so this is an absence of information, not a rejection. |
| anything else (incl. `252`) | UNKNOWN | `252` means the server states outright that it cannot verify. |

This changes ADR-0004's rule rather than implementing it, so it requires
ADR-0007. It is arguably closer to ADR-0004's *reasoning* than to its
wording: 0004's Context justifies UNKNOWN by naming servers that
"greylist, rate-limit, or flatly refuse" probes, and greylisting and
rate-limiting are both 4xx.

Known limitation to state plainly in ADR-0007: some servers return `550`
for greylisting instead of the correct `451`, so 5xx is strong evidence
rather than proof.

### Changes

- `app/core/verifier.py` — replace the two-way branch with the three-way
  classification. `smtp_ok` keeps its current meaning (`code == 250`).
  `error` is populated with the reply code on any non-250 so the reason
  survives into the results table and CSV.
- `docs/adr/0007-smtp-response-classification.md` — new, Status
  `Accepted — supersedes 0004`, MADR-lite body, citing RFC 5321 and the
  4xx/5xx distinction.
- `docs/adr/0004-verification-staging-unknown-not-invalid.md` — Status line
  changed to `Superseded by 0007`. **Body untouched**, per the project's ADR
  immutability rule.
- `docs/adr/README.md` — index row for 0007, Status column for 0004 updated.
- `ROADMAP.md` — tick the v0.25 verifier item; v0.25 stays `In Progress`
  (CI pipeline and CONTRIBUTING.md remain open).

### Tests

The non-250 path has no coverage today and cannot get any without mocking,
since the only SMTP test is `@pytest.mark.smtp` and accepts VALID or UNKNOWN
either way. Add offline tests to `tests/test_verifier.py` that monkeypatch
`smtplib.SMTP` (and the MX lookup) and assert:

- `250` → VALID, `smtp_ok is True`
- `550` → INVALID, `error` contains the code
- `450` → UNKNOWN
- `421` → UNKNOWN
- `252` → UNKNOWN

These require no network and run under `pytest -m "not smtp"`.

## Part B — `app/core/pipeline.py`

### Problem

The crawl → extract → generate loop lives only inside
`CrawlerWorker._crawl()`, and the verify loop only inside
`VerifierWorker.run()`. Both are `QThread` subclasses. A CLI cannot reuse
either without importing Qt or copy-pasting the logic.

### Decision

Extract both loops into `app/core/pipeline.py` as plain async/sync
generators with no Qt dependency, and have both the CLI and the existing
workers consume them. The workers become thin signal adapters.

### API

```python
@dataclass
class Discovery:
    email: str
    source_url: str
    generated: bool          # True = pattern-generated candidate

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
) -> AsyncGenerator[Discovery, None]: ...

def verify_all(
    emails: list[tuple[str, str]],
    *,
    smtp_enabled: bool = True,
    api_key: str | None = None,
) -> Iterator[dict]: ...
```

Design notes:

- The de-duplication `seen` set, the target-domain filter, and the
  `request_delay` sleep all move out of `CrawlerWorker` into
  `crawl_and_extract`.
- `on_page` exists because the GUI needs per-page progress and debug lines;
  the CLI uses it to print progress to stderr. A callback keeps the
  generator's yield type single-purpose instead of forcing an event union
  that every consumer would have to dispatch on.
- `should_stop` is checked once per **page**, not per yielded `Discovery`.
  `CrawlerWorker` today checks its stop flag every page, so a consumer that
  could only break on a yielded result would keep crawling through pages
  containing no email addresses after Stop was pressed. `verify_all` needs
  no equivalent, because it yields exactly once per input address and a
  consumer-side `break` is already page-equivalent there.
- `verify_all` yields the record dict the worker builds today
  (`email`, `source`, `status`, `error`) so `exporter.export_valid()` and
  the results table need no changes. The `VStatus` → string mapping moves
  from `VerifierWorker` into `pipeline`.

### Worker refactor

- `CrawlerWorker._crawl()` — iterate `crawl_and_extract`, emit
  `email_found` or `candidate_found` per `Discovery.generated`, pass
  `on_page` to emit `debug_message` and `page_crawled`, break on stop flag.
- `VerifierWorker.run()` — iterate `verify_all`, emit `result_ready` and
  `progress`, break on stop flag, emit `verify_finished` with the list.

`app/ui/` is untouched: the worker signal contract does not change.

`app/workers/` and `app/ui/` have no automated tests by design (ADR-0002),
so this refactor is verified by launching `python -m app.main` and running a
real crawl and verify.

## Part C — `app/cli.py`

### Shape

Three subcommands, stdlib `argparse`, no new dependencies:

```
python -m app.cli discover <domain> [--max-seeds N] [--no-duckduckgo]

python -m app.cli scan <domain> [--seeds FILE] [--pattern "{first}.{last}"]
                                [--max-pages N] [--concurrency N] [--delay S]
                                [--phase2] [--phase1-timeout S] [--no-smtp]
                                [--output PATH] [--no-session] [--quiet]

python -m app.cli verify --input FILE|- [--no-smtp] [--output PATH]
```

`--version` on the root parser.

Behaviours that the flag list alone leaves ambiguous:

- `scan` always runs the full pipeline, verification included. `--no-smtp`
  toggles only the SMTP stage inside `verify()`, exactly as the GUI's
  Quick/Deep setting does — it does not skip verification.
- `scan --seeds FILE` skips seed discovery entirely and reads seed URLs
  from the file, one per line, blank lines and `#` comments ignored. The
  positional `<domain>` is still required, since it is the email-domain
  filter, not just the discovery input.
- `verify --input` reads one email address per line, ignoring blank lines
  and `#` comments. It also accepts the TSV that `scan` emits, taking the
  first tab-separated field, so `scan ... > out.tsv` then
  `verify --input out.tsv` round-trips without an intermediate `cut`.
  Source URLs are empty for addresses supplied this way unless a second
  field is present.

### Language

Spanish for all human-readable text (help, progress, errors, summaries);
English for subcommand and flag names. This follows CLAUDE.md's existing
treatment of GitHub topics: fixed interface identifiers are not
translatable prose, while everything a user reads is Spanish.

### Streams

- **stdout — data only.** `discover` writes one seed URL per line.
  `scan` and `verify` write tab-separated `email<TAB>status<TAB>source`,
  so `cut -f1` yields a clean address list.
- **stderr — everything human.** Progress, detected entity type, hardware
  tier, counts, warnings, errors. `--quiet` silences all of it.

This split is what makes the CLI pipeable, and it is why the GUI's
Desktop auto-export is deliberately never triggered from the CLI:
`exporter.default_export_path()` calls `desktop.mkdir(parents=True,
exist_ok=True)`, which would create a phantom `~/Desktop` on a headless
server. `--output PATH` calls `export_valid(results, path)` explicitly.

### Defaults

`hw_profile.get_hw_profile()` supplies `concurrency`, `request_delay` and
`max_pages`; the detected tier is reported on stderr. Explicit flags
override the profile.

### Persistence

`scan` and `verify` write to `~/.radarcl/sessions.db` via the existing
`session` module by default, inheriting ADR-0006's last-10 pruning as
PRD.md's constraints section requires. `--no-session` suppresses all
writes, for cron and CI.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Completed (including "completed, found nothing") |
| 1 | Runtime error (unreachable target, unwritable output path) |
| 2 | Usage error (argparse default) |
| 130 | Interrupted with Ctrl+C |

On `KeyboardInterrupt` the crawl stops, whatever was already collected is
still written to stdout and to `--output` if given, and the exit code is
130. A partial result is more useful than a discarded one for a crawler.

### Tests

`tests/test_cli.py`, all offline:

- `build_parser()` defaults and flag overrides for each subcommand.
- TSV row formatting.
- `verify --input` reading from a file and from stdin (`-`).
- **Qt guard:** import `app.cli` and assert `"PySide6" not in sys.modules`.
  This makes the architecture rule enforceable rather than aspirational.

`tests/test_pipeline.py`, all offline:

- `crawl_and_extract` deduplicates repeated addresses and honours the
  target-domain filter, driven by a monkeypatched `Crawler` yielding
  canned HTML.
- `verify_all` produces the expected record dicts from a monkeypatched
  `verify()`.

## Part D — Docs and packaging

- **`requirements-core.txt`** — new. Lists only what `app/core/` actually
  imports: `httpx[http2]`, `beautifulsoup4`, `lxml`, `dnspython`, `psutil`.
  No PySide6, no PyInstaller. This is what makes the core-as-library claim
  real: a headless user installs five packages, not a GUI toolkit.
  `requirements.txt` is left alone.
- **`README.md`** — new "Uso desde la línea de comandos" section with the
  three subcommands and a piping example; new "Uso como biblioteca" section
  with a runnable `from app.core.seed_discoverer import discover_seeds`
  example. Platform badge updated to distinguish the Windows GUI from the
  headless CLI. Version history gains v0.3.0. Spanish, and subject to the
  AI-tell final pass since the README is outward-facing copy.
  **Do not claim tested Linux/macOS support** — the accurate claim is that
  the CLI has no Qt dependency, not that other platforms have been verified.
- **`CLAUDE.md`** — document `app/cli.py` and `app/core/pipeline.py` in the
  Architecture section; add the CLI invocations to Commands. English, as a
  developer-facing file.
- **`pyproject.toml`** — version `0.2.0` → `0.3.0`.
- **`ROADMAP.md`** — v0.30 marked `Done`; v0.25 `In Progress` with one of
  three items ticked; new catch-all bullet added under v0.55 (below).

## Out of scope, recorded not dropped

- **Accept-all / synthetic-250 detection.** Research for this design found
  that Yahoo, AOL and mail.com return `250` to every `RCPT TO` as
  anti-harvesting, and hardened Exchange estates do the same — so
  `250 → VALID` produces false *positives* on accept-all domains. Detecting
  it needs a second probe to a random address at the same domain and a
  fourth status bucket, which deserves its own ADR. Added to ROADMAP under
  v0.55 (Verifier Stage 4 resolution), not implemented here.
- **JSON/HTML output** — that is v0.35. The CLI ships TSV on stdout and CSV
  via `--output`, both of which already exist.
- **CI pipeline and CONTRIBUTING.md** — the other two v0.25 items, untouched.
- **`keyring` and `aiofiles`** — imported nowhere in the repo, but removing
  them is unrelated cleanup and was explicitly kept out of this change.

## Order of work

1. Verifier tests (failing) → verifier fix → ADR-0007 + 0004 status flip.
2. `pipeline.py` tests (failing) → `pipeline.py` → worker refactor →
   manual GUI verification.
3. `cli.py` tests (failing) → `cli.py`.
4. Docs, `requirements-core.txt`, version bump, ROADMAP.
