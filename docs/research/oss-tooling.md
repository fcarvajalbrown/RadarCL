# OSS tooling research — inspiration for RadarCL's growth

Findings from 20 web searches (2026-07-24) into open-source libraries and
tools adjacent to RadarCL's problem space: async crawling, subdomain/seed
discovery, email extraction and verification, packaging, and open-source
project maintenance. This is inspiration, not an adoption plan — nothing
here is installed or required. Where a finding maps to an existing
`app/core/` module or a ROADMAP.md phase, that's noted directly.

## Aspirational reference: Subfinder

Subfinder (ProjectDiscovery) is the explicit north star for what RadarCL
should grow toward. Three traits worth naming directly:

- **Permissive license, zero adoption friction.** Subfinder is MIT;
  RadarCL is now Apache 2.0 (same direction — broad reuse, no barrier for
  government/institutional users who often can't touch copyleft code at
  all, per the civic-tech licensing research above).
- **One job, done fast, via many passive sources in parallel.** Subfinder
  hits dozens of passive sources concurrently (CT logs, DNS aggregators,
  search engines, archive.org). RadarCL's `seed_discoverer.py` already does
  the same *shape* of thing — a cascading pipeline of passive sources
  (crt.sh, DNS liveness, DuckDuckGo) — just with far fewer sources today.
  Growing that source list is the most direct way to close the gap.
- **Composable core, not a monolith.** Subfinder is a focused CLI/library
  that plugs into a bigger toolkit (ProjectDiscovery's httpx, nuclei, etc.).
  RadarCL's `app/core/` is already Qt-free and independently usable (see
  [ADR-0002](../adr/0002-async-core-qthread-worker-bridge.md)), but the
  project currently presents itself GUI-first. Leaning further into
  `core` as a standalone, importable piece — not just an implementation
  detail behind the desktop app — is the structural change that would
  actually make the Subfinder comparison hold up.

## Crawling and scraping

- **Scrapy** — the established large-scale crawling framework; built-in
  async engine, request scheduling, and middleware (retries, rate limiting,
  robots.txt). RadarCL's `app/core/crawler.py` reimplements a much smaller
  subset of this by hand (see [ADR-0003](../adr/0003-crawl-phase1-phase2-scope.md)
  for why it's deliberately narrow-scoped). Worth a look if crawl
  scope ever grows beyond .cl-only sites.
- **httpx vs aiohttp vs curl_cffi** — RadarCL already uses httpx (async +
  sync in one client, HTTP/2). Benchmarks suggest aiohttp pulls ahead past
  ~200 concurrent requests, which RadarCL's hardware-tiered concurrency caps
  (see [ADR-0005](../adr/0005-hardware-aware-auto-tuning.md)) never approach
  in practice. curl_cffi is the relevant one to know about *if* a target
  site starts blocking on TLS fingerprint — it impersonates real browser
  TLS behavior, which plain httpx can't do.
- **Playwright** — dominant headless-browser scraper (faster than Selenium,
  handles JS-rendered content httpx/BeautifulSoup can't see at all). Real
  cost: a single Chromium instance runs 200-500MB RAM, directly in tension
  with RadarCL's low-spec-hardware design goal. Relevant only if a specific
  target site turns out to be JS-rendered and worth a special-cased fallback,
  not as a default.
- **Protego** (Scrapy's own robots.txt parser) — pure-Python, handles
  wildcards, crawl-delay, and request-rate directives that the stdlib
  parser misses. Directly relevant: `Crawler.respect_robots` in
  `app/core/crawler.py` is currently a documented no-op placeholder. This is
  the natural library to implement it with, if/when that's prioritized.

## Seed / subdomain discovery

- **subfinder** (ProjectDiscovery) — passive subdomain enumeration across
  dozens of sources in parallel (CT logs, DNS aggregators, search engines,
  archive.org). Faster than `app/core/seed_discoverer.py`'s single crt.sh
  query + DNS verify, at the cost of being a Go binary dependency rather
  than pure Python.
- **OWASP Amass** — heavier-weight alternative; deeper infra/graph analysis,
  more data sources (many needing API keys). Overkill for RadarCL's current
  single-purpose seed discovery, but the source list itself (Censys,
  SecurityTrails, Netlas, etc.) is a useful reference for what
  `_KNOWN_SOURCES` in `seed_discoverer.py` could eventually expand to.
- **CertSpotter / MerkleMap** — listed here in the original survey as
  interchangeable Certificate Transparency alternatives to crt.sh. Measuring
  them on 2026-07-24 for v0.40 showed they are not comparable. CertSpotter
  answers unauthenticated in 0.6s (ten full-domain queries an hour, then 429)
  and is now the fallback; MerkleMap returns 401 without an API key and costs
  EUR 49/month with no free tier, so it was rejected. CertSpotter's free tier
  also serves unexpired certificates only, which is why it found 4 hostnames
  for `nunoa.cl` against crt.sh's 13. See
  [ADR-0011](../adr/0011-ct-fallback-and-source-hygiene.md).

## Email harvesting and verification (inspiration, not the model)

- **theHarvester** — the closest existing OSS analog to RadarCL's overall
  purpose: harvests emails/subdomains/names from public sources via
  pluggable modules. Good reference for module/source design, though its
  scope (any TLD, any target) is broader than RadarCL's deliberate .cl-only
  focus.
- **SpiderFoot / Belati** — broader OSINT aggregation frameworks with
  modular plugin architectures; useful as prior art for how a plugin system
  *could* look if RadarCL ever wanted pluggable data sources instead of the
  current hardcoded cascade in `discover_seeds`.
- **email-validator (JoshData)** — RFC 5322 syntax + deliverability checks;
  a more standards-complete syntax validator than the regex in
  `app/core/verifier.py`. Could tighten Stage 1 (syntax) if edge cases in
  the current regex ever cause problems.
- **disposable-email-domains** — a maintained, daily-updated list of 70k+
  disposable/temp-mail domains. Not really relevant to RadarCL's target
  (municipal/institutional `.cl` addresses are never disposable-service
  domains), but worth knowing about if scope ever expands to general public
  signup-style email hunting.
- **aiodns** — a pycares-based async DNS resolver, positioned as
  lighter-weight than dnspython for simple concurrent lookups, though best
  suited to long-lived resolver instances (dnspython's own async modules
  cover the same need with more record-type flexibility, e.g. MX). Not an
  obvious swap for `app/core/verifier.py`'s MX stage today, but relevant if
  DNS-lookup volume ever becomes the bottleneck.

## Scale-out (maps to ROADMAP.md Phase 1: "cloud-based crawling")

- **Celery + Redis** — the standard distributed task queue pairing;
  workers pull crawl jobs from a shared Redis-backed queue, enabling
  crawling from multiple machines/IPs. Directly relevant to the Phase 1
  "cloud-based crawling to bypass IP blocks" item (see
  [ADR-0005](../adr/0005-hardware-aware-auto-tuning.md) — that ADR's own
  hardware-tiering assumptions would need revisiting under this model).
- **Scrapy-Redis** — same idea, but built specifically for Scrapy's
  scheduler/dedup, letting multiple spider instances share one queue. Only
  relevant if a future rewrite moves RadarCL's crawler onto Scrapy itself.

## Packaging (already-shipped v1.0 concerns, not urgent)

- **PyInstaller vs Nuitka vs Briefcase** — RadarCL currently uses
  PyInstaller (see [ADR-0001](../adr/0001-pyside6-gui-stack.md)). Nuitka
  transpiles to C and compiles natively — better decompilation resistance
  and fewer antivirus false-positives (a real, currently-unsolved problem
  for a `.exe` PyInstaller ships to non-technical municipal users), but
  packaging is markedly slower. Briefcase (BeeWare) instead produces
  platform-native installers (MSI/.app/AppImage) without native compilation.
  Worth a look specifically for the AV-false-positive angle if that becomes
  a real user complaint.

## PySide6/Qt ecosystem

- **QtAwesome** — bundles Font Awesome, Material Design Icons, Phosphor,
  etc. as iconic fonts usable directly in PySide6 widgets; ships a
  `qta-browser` icon picker. Could replace the emoji-as-button-icon
  approach currently used in `app/ui/control_panel.py` (▶, ⏸, ⏹, ✕, ↺) with
  proper scalable icons.
- **PyQtDarkTheme / QDarkStyle** — flat dark/light theming that syncs with
  the OS theme and is PyInstaller-compatible. Relevant only if a dark mode
  is ever requested — not on the current roadmap.
- **pytest-qt** — a pytest plugin for PyQt/PySide testing (`qtbot` fixture,
  signal-waiting helpers, headless — no display needed, so it runs fine in
  CI). RadarCL's `tests/` currently only covers `app/core/` (Qt-free by
  design, see [ADR-0002](../adr/0002-async-core-qthread-worker-bridge.md));
  pytest-qt is the natural tool if `app/ui/`/`app/workers/` ever get test
  coverage too.

## Project maintenance / discoverability tooling

- **GitHub Actions Python CI template** — standard `actions/setup-python` +
  pytest workflow; RadarCL has no `.github/workflows/` yet, so this is
  straightforward to add (run `pytest -m "not smtp"` on push).
- **Dependabot with pre-commit support** (new as of March 2026) —
  Dependabot can now open PRs to bump `rev:` pins in
  `.pre-commit-config.yaml` directly, not just `requirements.txt`. Relevant
  once/if a `.pre-commit-config.yaml` exists.
- **shields.io** — the standard badge service for READMEs (build status,
  license, version). Directly usable in the Phase 0 README rewrite.
- **semantic-release** — automates version bumps + changelog generation
  from commit message conventions. Bigger process commitment (requires
  consistent commit conventions) than RadarCL's current single-maintainer
  workflow needs right now.

## Chilean/regional open-data context

- **datos.gob.cl** — Chile's national open-data portal; hosts datasets from
  ministries, public services, and municipalities. Also fronts specific
  APIs (ChileCompra for procurement, BCN for legislative bills, INE for
  statistics). As of the last public count, roughly half of Chile's 345
  comunas were registered there — a potential *alternative or
  supplementary* seed source to crt.sh/DuckDuckGo in `seed_discoverer.py`,
  though coverage is inconsistent enough that it can't replace the existing
  cascade.
- Broader Latin American civic-tech landscape: government innovation labs
  (Chile included) and civil-society transparency projects are active
  through the region, but the search didn't surface a specific named OSS
  project directly comparable to RadarCL's narrow email-discovery focus —
  theHarvester (above) remains the closest analog.

## Sources

- [Web Scraping Tools Comparison 2026: requests vs curl_cffi vs Playwright vs Scrapy](https://dev.to/vhub_systems_ed5641f65d59/web-scraping-tools-comparison-2026-requests-vs-curlcffi-vs-playwright-vs-scrapy-2fad)
- [Scrapy vs Playwright: Which to Choose for Web Scraping in 2026](https://dev.to/agenthustler/scrapy-vs-playwright-which-to-choose-for-web-scraping-in-2026-566n)
- [crt.sh Alternatives 2026 — Certificate Transparency](https://enterno.io/en/s/alternatives-crt-sh)
- [Reconnaissance 102: Subdomain Enumeration — ProjectDiscovery Blog](https://projectdiscovery.io/blog/recon-series-2)
- [GitHub - laramies/theHarvester](https://github.com/laramies/theHarvester)
- [theHarvester OSINT Tool Alternatives - SaaSHub](https://www.saashub.com/theharvester-osint-tool-alternatives)
- [GitHub - JoshData/python-email-validator](https://github.com/JoshData/python-email-validator)
- [GitHub - disposable-email-domains/python-disposable-email-domains](https://github.com/di/disposable-email-domains)
- [GitHub - aio-libs/aiodns](https://github.com/aio-libs/aiodns)
- [Asynchronous I/O Support — dnspython documentation](https://dnspython.readthedocs.io/en/latest/async.html)
- [Playwright Web Scraping Tutorial for 2026](https://oxylabs.io/blog/playwright-web-scraping)
- [Distributed Web Crawling With Python, Celery & Redis](https://medium.com/@datajournal/distributed-web-crawling-51012c760bee)
- [GitHub - rmax/scrapy-redis](https://github.com/rmax/scrapy-redis)
- [Python packaging comparison: Nuitka vs PyInstaller](https://inf.news/en/tech/73e49bc3890cc7596d7a1e851222c2c4.html)
- [How to package a python desktop app for Windows with briefcase](https://medium.com/@nohkachi/how-to-package-a-python-desktop-app-for-windows-with-briefcase-a270cf05da17)
- [GitHub - spyder-ide/qtawesome](https://github.com/spyder-ide/qtawesome)
- [GitHub - 5yutan5/PyQtDarkTheme](https://github.com/5yutan5/PyQtDarkTheme)
- [GitHub - pytest-dev/pytest-qt](https://github.com/pytest-dev/pytest-qt)
- [Building and testing Python - GitHub Docs](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [Dependabot now supports pre-commit hooks - GitHub Changelog](https://github.blog/changelog/2026-03-10-dependabot-now-supports-pre-commit-hooks/)
- [GitHub - badges/shields](https://github.com/badges/shields)
- [semantic-release/semantic-release](https://github.com/semantic-release/semantic-release)
- [datos.gob.cl - Data Portals](https://dataportals.org/portal/chile-government/)
- [Open government, civic tech and digital platforms in Latin America](https://onlinelibrary.wiley.com/doi/10.1111/isj.12468)
- [Pure-Python robots.txt parser (Protego) - PyPI](https://pypi.org/project/Protego/0.3.0)
- [HTTPX vs. Requests vs. AIOHTTP: Complete Comparison Guide (2026)](https://decodo.com/blog/httpx-vs-requests-vs-aiohttp)
