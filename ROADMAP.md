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
— the stub was stale, not accurate. See [PRD.md](docs/PRD.md) for the vision,
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
**Status:** Done
- [x] JSON and HTML export alongside the existing CSV auto-export
      (`app/core/exporter.py`) — output-format parity with theHarvester,
      and the natural output surface for CLI mode. Format comes from the
      `--output` extension, overridable with `--format`; both the CLI and
      the GUI go through one `export()` entry point.
- [x] Contents differ by format: CSV stays VALID-only, JSON and HTML carry
      every record with its status and the `error` explaining it. A
      valid-only file discards exactly the rows worth retrying, which is
      the failure mode
      [ADR-0009](docs/adr/0009-mx-resolution-failure-is-unknown.md)
      documented. See
      [ADR-0010](docs/adr/0010-export-contents-differ-by-format.md).
- [x] HTML is a single self-contained report — inline CSS, no JavaScript,
      no external asset — so it opens on a machine with no network, the
      same stance [ADR-0008](docs/adr/0008-vendored-core-dependencies.md)
      takes on dependencies.
- [x] GUI strings finished in Spanish. `control_panel.py`,
      `results_table.py` and `terminal_panel.py` still held English labels,
      status messages and dialogs from before the translation rule, which
      contradicted CLAUDE.md's standing language rule.

**Relevant ADRs:** [0010](docs/adr/0010-export-contents-differ-by-format.md)
(why a CSV and a JSON of the same run legitimately disagree on row count).

### v0.40 — Source breadth (Chile-curated)
**Status:** Done
- [x] CertSpotter as a crt.sh fallback inside `seed_discoverer.py`'s stage 1,
      which previously failed silently with no fallback at all. `_ct_subdomains`
      tries each source in order and stops at the first non-empty result;
      only an all-sources failure raises, and `discover_seeds` catches that so
      the stage still fails silently as a stage. Timeouts cut to 20s and 10s
      after measuring crt.sh at 60-77s cold and CertSpotter at 0.6s.
- [x] **MerkleMap rejected, do not retry it.** `api.merklemap.com/v1/search`
      returns 401 without a key and the only plan is EUR 49/month with no free
      API tier. `rapiddns.io` was measured as a possible third source (8 names
      for `nunoa.cl`, five absent from crt.sh) and deferred: it is HTML
      scraping with no API contract. See
      [ADR-0011](docs/adr/0011-ct-fallback-and-source-hygiene.md).
- [x] The curated-source stage was rebuilt, guarded, measured and then
      removed. Its eight hardcoded entries were first replaced after five
      turned out wrong or dead (`transparencia.cl` a content blog,
      `munitel.cl` a real-estate site, `cna.cl` an arbitration centre,
      `fach.cl` the Air Force and unreachable), and a live `smtp`-marked
      test was added so a source that keeps answering 200 while becoming
      something else fails too
      ([ADR-0012](docs/adr/0012-curated-sources-assert-identity.md)).
- [x] Measuring the stage end to end then showed it returns nothing. Its
      link scoring never fired: no curated homepage carries an anchor
      naming the target, across all thirteen source-target pairs. Crawling
      the twelve sources alone for 451 pages harvested 97 `.cl` addresses
      and not one belonging to any of eight targets. On seven of those
      eight, `max_seeds=20` truncation discarded the stage's seeds
      entirely; on the eighth they took 60% of the crawl budget for no
      addresses. The stage, `_KNOWN_SOURCES` and the identity guard were
      removed, and DuckDuckGo moved up to stage 4
      ([ADR-0013](docs/adr/0013-curated-source-stage-removed-after-measurement.md)).
- [x] `crawler.py` sends the browser User-Agent, reversing ADR-0011's split.
      `portaltransparencia.cl` and `anid.cl` answer 403 to the old token, so
      the crawler fetched zero pages from two sites the stage was seeding it.

So v0.40 shipped the Certificate Transparency half of its source-breadth
goal and disproved the other half. The curation claim in
[PRD.md](docs/PRD.md) has no implementation behind it as of this version.

**Relevant ADRs:** [0011](docs/adr/0011-ct-fallback-and-source-hygiene.md)
(why the chain returns empty instead of raising when a source has no records;
its curated-source half is now void),
[0012](docs/adr/0012-curated-sources-assert-identity.md) (superseded, kept
for the drift-detection measurements it records),
[0013](docs/adr/0013-curated-source-stage-removed-after-measurement.md) (the
measurement, and why a stage that cannot be shown to contribute is removed
rather than maintained).

### v0.50 — page evidence, and the `.com` question closed
**Status:** Done
- [x] The filter change this item asked for does not ship, and the
      measurement that closed it does. Chilean `.com` sites yield 0.00-0.05
      addresses per page; `codelco.com`'s only two finds were `.cl`
      addresses already collected today. The one target where a `.com`
      filter pays off is `teck.com`, the Canadian one. "Add `.com`" was
      intuitive and would have imported a foreign address book while adding
      nothing on Codelco, Falabella or Sonda.
- [x] `app/core/provenance.py`: `chile_evidence` reports which Chilean
      signals a page carried — `lang-es-cl`, `rut`, `phone-cl`, `lexicon`,
      `path-cl`. It is a flag on `Discovery`, never a filter: at 57% recall
      a filter would silently discard real addresses on 43% of
      Chilean-owned sites.
- [x] The claim is about the **page**, not about who owns the company.
      `teck.com` fires because its contact page lists a Santiago office,
      and that is correct. Six further signals were tested and rejected,
      including `hreflang="es-CL"`, which in the sample fired only on a US
      company.
- [x] The `.cl` filter on scraped addresses is unchanged. A non-`.cl`
      address is emitted only when the user names that domain, which the
      pattern-generation path had been doing silently since it shipped —
      `PRD.md` called the filter a permanent boundary and the code had
      never enforced it.
- [x] Evidence reaches the JSON and HTML exports. CSV keeps the columns
      [ADR-0010](docs/adr/0010-export-contents-differ-by-format.md) gave
      it, and the CLI's stdout keeps its three-field piping contract.
- [x] `python-stdnum` and `phonenumbers` vendored per
      [ADR-0008](docs/adr/0008-vendored-core-dependencies.md).
      libphonenumber accepts the US ZIP+4 `99201-0301` as a Chilean mobile,
      which is guarded explicitly.

**Relevant ADRs:** [0014](docs/adr/0014-country-is-never-inferred-from-a-com-address.md)
(why a `.com` address carries no country, and why the remedy annotates
rather than decides). Narrows
[0003](docs/adr/0003-crawl-phase1-phase2-scope.md) rather than superseding
it. Evidence and sample limits are in
[docs/research/dotcom-attribution.md](docs/research/dotcom-attribution.md).

### v0.55 — Verification honesty
**Status:** Done
- [x] The Stage 4 API placeholder is closed and removed, not built. No
      interface exposed it, `api_status` was read by nothing, and the early
      return on `smtp_enabled` meant it could only fire after a completed
      SMTP probe. Free tiers run 100 verifications a month and the paid
      providers are 70-85% accurate on catch-all domains, which is the case
      immediately below this one, so the integration would have cost money
      to be unreliable exactly where it was needed
      ([ADR-0015](docs/adr/0015-no-third-party-verification-api.md)).
- [x] Catch-all domain detection. A `250` from a server that also accepts
      invented addresses is now `VStatus.CATCH_ALL`, not VALID: two probes
      of 20 hex characters each, over the connection already open, with
      every probe having to be accepted before the verdict lands. Cached
      per domain for the run, since catch-all is a property of the server
      and not of the mailbox. Excluded from the CSV and present in JSON and
      HTML, the split ADR-0010 already drew
      ([ADR-0016](docs/adr/0016-catch-all-domains-are-not-valid.md)).

### v0.60 — Reaching the right domain
**Status:** In Progress — item 1 resolved (declined on measurement,
[ADR-0019](docs/adr/0019-the-sibling-cl-hint-is-measured-and-declined.md)),
item 2 not started. The version is not shippable and no `0.6.0` tag exists;
`app/__init__.py` is still `0.5.5`.

Two items about finding the target rather than crawling it. The first is
measured and comes first for that reason; the second is not measured at
all, and [ADR-0013](docs/adr/0013-curated-source-stage-removed-after-measurement.md)
is what happens when an obvious-sounding source ships unmeasured.

The first has now been measured and declined. That is the second time a
v0.x item has died on its own measurement rather than on an argument, after
the curated-source stage in v0.40, and both times the intuition was that the
feature was obviously worth having.

- [x] **Sibling `.cl` mail-domain hint — measured, and it does not ship.**
      The item asked that a non-`.cl` target trigger a check of whether
      `<base>.cl` has a mail-capable MX. A threshold was committed before
      the run: ship only if the 95% interval's lower bound reached 40%.

      It reached **39.994%**. Drawn at random from a Wikidata frame of 334
      Chilean organisations on a non-`.cl` primary domain, 84 of 178
      reachable siblings were mail-capable — 47.2%, 95% Wilson
      [39.99%, 54.51%].

      The margin is meaningless; the reason it does not ship is the next
      number. `resolve_mx` honours RFC 5321's implicit MX, so a domain with
      a web server and no mail service counts as mail-capable, and **26 of
      those 84 have no MX record at all** — `facebook.cl`, `columbia.cl`,
      `roche.cl`, `sonda.cl` among them. Requiring a real MX record gives
      **58 of 178 = 32.6%, [26.1%, 39.8%]**, an interval lying entirely
      below the gate. The hint fails once it has to mean what it says.

      A census of Consejo Minero's 9 non-`.cl` member domains gives 6 of 8
      reachable, 75%, all with real MX records. So the sibling is normal
      among large corporates and uncommon across Chilean organisations
      generally, which is why ADR-0018's 8-of-13 pilot read high: it was a
      corporate sample. The tool cannot know which population a user is
      pointing at.

      Full frame, seed, intervals, non-response and cost are in
      [docs/research/sibling-cl-prevalence.md](docs/research/sibling-cl-prevalence.md);
      the decision is
      [ADR-0019](docs/adr/0019-the-sibling-cl-hint-is-measured-and-declined.md).

      **Correction, recorded rather than quietly fixed.** This section used
      to say EUIPO "measured cybersquatting at 49% of major brands with 26%
      of squatted domains on ccTLDs". Neither half survives reading the
      study: the 49% is 486 of 993 analysed brand-related *domain names*
      judged suspicious, across 20 brands of small, medium and large
      entities; the 26% is the ccTLD share of all analysed domains, not of
      the suspicious ones. The on-point figure is that **116 of 257
      brand-related ccTLD domains, 45%, were suspicious** — which makes the
      ownership caveat better than the number being quoted did.
- [ ] **PGP keyserver lookup** as a new email source in
      `seed_discoverer.py` — direct theHarvester parity, plausible fit for
      `.cl` government and institutional contacts who publish keys.
- [ ] Measure recovered addresses per page spent before building the PGP
      source. This was v0.45 until v0.50 shipped, which left an unstarted
      version sitting behind a released one; renumbered rather than left
      as a gap.

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
Tag once v0.25 → v0.90 are shipped and [PRD.md](docs/PRD.md)'s success criteria
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
