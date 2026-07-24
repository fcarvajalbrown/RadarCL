# ROADMAP

Phase-based, not calendar-dated. Status values: `Not Started`, `In Progress`,
`Blocked`, `Done`.

## Phase 0 — Discoverability & branding
**Status:** In Progress — reopened; README/branding still lags the quality
bar other project agents (e.g. MuniANCI's) have hit. Next agent should
focus specifically on closing that SEO/discoverability/branding gap.

Make RadarCL findable and legible to the audience it's actually useful to:
developers building civic-tech, govtech, or OSINT-style tooling around
Chilean (.cl) data.

- [x] README rewrite: lead with what RadarCL does technically (async .cl
      crawler → extraction/de-obfuscation → cascading seed discovery →
      staged verification), then who it's for.
- [x] GitHub repo description: one keyword-forward sentence, ~150 chars.
- [x] GitHub topics: 8, mixing broad (`python`, `osint`, `web-scraping`,
      `dns`) and narrow (`chile`, `email-verification`, `pyside6`,
      `certificate-transparency`) terms — verified real `/topics/<name>`
      repo counts (213-799k) before committing, per the researched guidance
      above.
- [x] Logo: embedded the existing `assets/icon.svg` as-is in the README
      header — no edits to the file itself.
- [x] License: added `LICENSE` (Apache 2.0) and set it in `pyproject.toml`,
      after weighing permissive vs. copyleft options (see
      `docs/research/oss-tooling.md`'s Subfinder-vs-theHarvester precedent)
      — this is a project decision, not a legal opinion; consult a lawyer
      before treating it as final given the personal-data angle.
- [x] Version: bumped `pyproject.toml` to `0.2.0` to match the actual
      current state (README's own roadmap section is due for a rewrite by
      another agent, hence 0.2 rather than 1.0).
- [x] README polish matching `MuniANCI`'s branding style: centered logo +
      title, badge row (version, license, platform, stack).
- [x] GitHub topics refined 8 → 10 (added `desktop-app`, `govtech`),
      staying inside global CLAUDE.md's 6-10 best-practice range —
      verified real `/topics/<name>` populated counts before committing
      (desktop-app 15,506; govtech 395).
- [x] README: added personal-credit + audience framing paragraph
      ("Desarrollado por Felipe Carvajal Brown, investigador
      independiente, para quienes construyen herramientas de
      civic-tech, govtech u OSINT...").
- [x] README: added "Aviso legal / uso responsable" section (no
      malicious use; project reserves the right to report abuse/pursue
      legal action) — disclaimer text, not legal advice; have a lawyer
      review if it needs to be enforceable.
- [x] README: added explicit "Licencia" section (previously only a
      badge, no callout).
- [x] README: added 5th signature badge (`alcance: solo .cl`).
- [x] Credit fix: replaced "Instituto Igualdad" with Felipe Carvajal
      Brown (personal, not institutional credit) everywhere it appeared
      — app window title (`app/ui/main_window.py`), Qt organization
      name (`app/main.py`), installer publisher + welcome text
      (`RadarCL.iss`), and the README line above.
- [x] Screenshot: considered, decided against — Felipe called it not
      needed; README stays text-only.

**Relevant ADRs:** [0001](docs/adr/0001-pyside6-gui-stack.md) (why it's a
desktop app, not a web tool — shapes how the README should pitch it),
[0003](docs/adr/0003-crawl-phase1-phase2-scope.md) (the .cl-only scope worth
stating plainly up front so it's not mistaken for a general-purpose scraper).

## v0.2 → v1.0 roadmap

Superseded the old "Phase 1 — Feature expansion" stub (2026-07-24): that
stub carried over three items from the README's "Planned Features v1.1"
list, but by the time this rewrite happened, pattern-based email generation
was already fully implemented and wired in (`app/core/pattern_generator.py`,
consumed by `app/workers/crawler_worker.py` and `app/ui/control_panel.py`)
— the stub was stale, not accurate. See [PRD.md](PRD.md) for the vision,
primary-audience, and competitive-positioning decisions this breakdown is
built on.

Versioned in 0.05 increments rather than broad phases, front-loading
cheap/high-credibility wins before the two genuinely large items (`.com`
scope, distributed crawling).

### v0.25 — Foundation / quality bar
**Status:** Done
- [x] CI pipeline: GitHub Actions running `pytest -m "not smtp"` on
      push/PR (`.github/workflows/tests.yml`), on ubuntu-latest with
      Python 3.12. Also verifies `vendor/` integrity via
      `scripts/vendor.py --check` and that the CLI starts.
- [x] Verifier fix: a non-250 SMTP response with no exception set
      `VStatus.INVALID` in `app/core/verifier.py`, contradicting
      [ADR-0004](docs/adr/0004-verification-staging-unknown-not-invalid.md).
      Now classified by reply-code class — 250 valid, 5xx invalid, 4xx and
      252 unknown — per
      [ADR-0007](docs/adr/0007-smtp-response-classification.md), itself
      later superseded by
      [ADR-0009](docs/adr/0009-mx-resolution-failure-is-unknown.md).
- [x] MX stage fix: a DNS resolver timeout was classified `INVALID`,
      identically to a nonexistent domain, so 16 real `@nunoa.cl`
      addresses were reported dead on a machine whose nameservers do not
      answer over UDP/53. Resolver failures are now `UNKNOWN`, and
      `app/core/dns_lookup.py` falls back from the system resolver to
      public nameservers to DNS-over-HTTPS. See
      [ADR-0009](docs/adr/0009-mx-resolution-failure-is-unknown.md).
- [x] Test markers: three verifier tests did live DNS lookups without the
      `smtp` marker, so `pytest -m "not smtp"` was not actually offline.
      Marker widened to mean live internet generally; offline suite now
      runs in ~5s instead of ~20s.
- [x] Dependency vendoring: core wheels committed to `vendor/` with a
      SHA-256 manifest and a hash-pinned `requirements-core.lock`, so a
      clean checkout installs with no network and survives a package being
      removed from PyPI. GUI deps hash-pinned but not vendored —
      `pyside6_addons` is 169 MB, over GitHub's 100 MiB per-file limit. See
      [ADR-0008](docs/adr/0008-vendored-core-dependencies.md).
- [x] `CONTRIBUTING.md` + issue/PR templates — in Spanish, matching the
      README, with the bug template warning contributors not to paste real
      harvested addresses into a public repository.

### v0.30 — Core-as-library / CLI mode
**Status:** Done
- [x] `app/cli.py`: headless entry point driving `app/core/` directly, no Qt
      — three subcommands (`discover`, `scan`, `verify`), stdout for data
      and stderr for Spanish progress. Enforced Qt-free by
      `tests/test_cli.py`.
- [x] README/docs reframe `app/core/` as independently importable, not just
      GUI plumbing — plus `app/core/pipeline.py` (shared by the CLI and the
      Qt workers) and `requirements-core.txt` for installing the core
      without PySide6.

**Relevant ADRs:** [0002](docs/adr/0002-async-core-qthread-worker-bridge.md)
(the Qt-free `core` boundary this mode is built on).

### v0.35 — Export flexibility
**Status:** Not Started
- [ ] JSON/HTML export alongside the existing CSV auto-export
      (`app/core/exporter.py`) — output-format parity with theHarvester,
      and the natural output surface for CLI mode.

### v0.40 — Source breadth (Chile-curated)
**Status:** Not Started
- [ ] CertSpotter/MerkleMap as crt.sh fallbacks in `seed_discoverer.py`'s
      `_crtsh_subdomains` (currently fails silently with no fallback).
- [ ] Expand curated Chile-specific sources beyond what's hardcoded today
      (`datos.gob.cl`, BCN, ChileCompra).

### v0.45 — PGP keyserver source
**Status:** Not Started
- [ ] Add PGP keyserver lookup as a new email source in `seed_discoverer.py`
      — direct theHarvester parity, plausible fit for `.cl`
      government/institutional contacts who publish PGP keys.

### v0.50 — `.com` domain support
**Status:** Not Started
- [ ] `.com` domain support for Chilean companies with international
      domains (e.g. `@bhp.com`, `@codelco.com`). Needs its own ADR before
      implementation — this revisits, not extends,
      [ADR-0003](docs/adr/0003-crawl-phase1-phase2-scope.md)'s `.cl`-only
      email filter, and per that ADR's own rules a changed decision gets a
      new ADR, never an edit to 0003 itself.

### v0.55 — Verifier Stage 4 resolution
**Status:** Not Started
- [ ] Resolve the Stage 4 API placeholder in `app/core/verifier.py`: either
      build a real third-party verification API integration, or close it
      formally with an ADR stating it's not planned. Currently an
      undecided placeholder, not a real deferred item.
- [ ] Accept-all / catch-all domain detection: Yahoo, AOL, mail.com and
      hardened Exchange estates return `250` to every `RCPT TO` as an
      anti-harvesting measure, so a 250 is not evidence the mailbox exists
      and the current code reports those as VALID. Needs a second probe to
      a random address at the same domain, a fourth status bucket, and its
      own ADR. Surfaced by the research behind
      [ADR-0009](docs/adr/0009-mx-resolution-failure-is-unknown.md).

### v0.65 — Distributed crawling, part 1: job distribution
**Status:** Not Started
- [ ] Job distribution across multiple workers/machines (Celery+Redis or a
      lighter alternative) — the orchestration layer cloud-based crawling
      needs before proxy rotation (v0.75) can do anything useful.
- [ ] New ADR revisiting [ADR-0005](docs/adr/0005-hardware-aware-auto-tuning.md)'s
      hardware-tiering assumptions under a multi-worker model.

### v0.75 — Distributed crawling, part 2: proxy rotation
**Status:** Not Started
- [ ] Proxy rotation with session-to-proxy binding — the actual
      IP-block-bypass mechanism (2026 state of the art per Crawlee's model),
      layered on top of the v0.65 job-distribution work.

### v0.90 — Hardening pass
**Status:** Not Started
- [ ] Docs refresh reflecting CLI mode, distributed crawling, and `.com`
      support once all three exist.
- [ ] `pytest-qt` coverage for `app/ui/`/`app/workers/` if time allows —
      currently only `app/core/` has tests, by design
      ([ADR-0002](docs/adr/0002-async-core-qthread-worker-bridge.md)).

### v1.0.0
Tag once v0.25 → v0.90 are shipped and [PRD.md](PRD.md)'s success criteria
hold.

## Beyond v1.0

Explicitly deferred, not forgotten:
- PyPI packaging (`pip install radarcl`) for the CLI/core — the Windows
  `.exe` stays the GUI distribution path.
- `Crawler.respect_robots` real implementation via Protego (currently a
  documented no-op placeholder) — considered for the pre-1.0 line during
  the 2026-07-24 roadmap brainstorm and deliberately left for later rather
  than dropped.
- AV-false-positive packaging fix — evaluate Nuitka or Briefcase as
  PyInstaller alternatives (see `docs/research/oss-tooling.md`).
- Pluggable/plugin data-source architecture (SpiderFoot-style) instead of
  the current hardcoded cascade in `seed_discoverer.py`.
- Dark mode / QtAwesome icons — cosmetic, not currently requested.
