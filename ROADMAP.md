# ROADMAP

Phase-based, not calendar-dated. Status values: `Not Started`, `In Progress`,
`Blocked`, `Done`.

## Phase 0 — Discoverability & branding
**Status:** In Progress

Make RadarCL findable and legible to the audience it's actually useful to:
developers building civic-tech, govtech, or OSINT-style tooling around
Chilean (.cl) data.

- [ ] README rewrite: lead with what RadarCL does technically (async .cl
      crawler → extraction/de-obfuscation → cascading seed discovery →
      staged verification), then who it's for.
- [ ] GitHub repo description: one keyword-forward sentence, ~150 chars.
- [ ] GitHub topics: 6-10, mixing broad (`python`, `osint`, `web-scraping`)
      and narrow (`chile`, `email-verification`, `pyside6`) terms — verify
      real `/topics/<name>` repo counts before committing to the list rather
      than assuming a topic slug resolving means it's populated.
- [ ] Logo: embed the existing `assets/icon.svg` as-is in the README header
      — no edits to the file itself.

**Relevant ADRs:** [0001](docs/adr/0001-pyside6-gui-stack.md) (why it's a
desktop app, not a web tool — shapes how the README should pitch it),
[0003](docs/adr/0003-crawl-phase1-phase2-scope.md) (the .cl-only scope worth
stating plainly up front so it's not mistaken for a general-purpose scraper).

## Phase 1 — Feature expansion
**Status:** Not Started

Carried over from the README's existing "Planned Features v1.1" list.

- [ ] `.com` domain support for Chilean companies with international domains
      (e.g. `@bhp.com`, `@codelco.com`).
- [ ] Pattern-based email generation for undisclosed addresses.
- [ ] Cloud-based crawling to bypass IP blocks.

Each item gets its own ADR once actually designed — none exist yet.

**Relevant ADRs:** [0003](docs/adr/0003-crawl-phase1-phase2-scope.md) (the
.cl-only email filter this phase's `.com` support item would need to revisit),
[0005](docs/adr/0005-hardware-aware-auto-tuning.md) (cloud-based crawling
changes the hardware-tuning assumptions this ADR is built on).
