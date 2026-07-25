# PRD

Stable vision/architecture/scope document. Rarely touched — phase-by-phase
planning lives in [ROADMAP.md](../ROADMAP.md), individual design decisions in
[docs/adr/](adr/).

Written retroactively at v0.2.0: RadarCL predates the PRD → ROADMAP → ADR
convention, so this captures what was already true plus what got decided
during the 0.2→1.0 roadmap brainstorm (2026-07-24), rather than a
pre-implementation spec.

## Problem

Finding and verifying public-contact `.cl` email addresses for Chilean
organizations (municipalities, government bodies, universities, companies)
is a manual, repetitive OSINT task. Generic tools either don't exist for
this specific domain-and-country combination, or are broad-scope
international tools (theHarvester, Subfinder, Amass) that treat `.cl` as
just another TLD rather than a domain with its own high-value sources
(Chilean Certificate Transparency patterns, municipal directory
conventions, `datos.gob.cl`, `transparencia.cl`) and naming conventions
worth modeling directly.

## Vision

RadarCL automates the full pipeline other OSINT/civic-tech tooling has to
assemble by hand for `.cl` targets: entity-aware seed discovery → phased
crawling → email extraction/de-obfuscation → pattern-based generation for
undisclosed addresses → staged, honest verification (syntax → MX → SMTP,
with UNKNOWN as a first-class outcome per
[ADR-0009](adr/0009-mx-resolution-failure-is-unknown.md)).

## Primary audience

External OSINT, civic-tech, and govtech developers building tools around
Chilean (`.cl`) data. RadarCL's origin was Instituto Igualdad's Área de
Innovación Tecnológica running its own campaigns — that origin story
motivated the initial feature set, but as of the 0.2→1.0 roadmap decision
it is not the design target going forward: features, docs, and packaging
decisions should optimize for outside adoption and legibility, not just
internal use.

## Non-goals

- **Not a general-purpose scraper.** The `.cl`-only email filter
  ([ADR-0003](adr/0003-crawl-phase1-phase2-scope.md)) is a permanent
  scope boundary, not a placeholder — even Phase-2 crawling of non-`.cl`
  pages only exists to *find* `.cl` addresses linked from them.
- **Not a hosted SaaS.** RadarCL ships as a local tool (Windows desktop
  `.exe` today, CLI mode from v0.30 onward) that the user runs themselves
  against their own network — not a service anyone can point at arbitrary
  targets.
- **Not committing to a cross-platform GUI.** PySide6/Qt6
  ([ADR-0001](adr/0001-pyside6-gui-stack.md)) stays a Windows-first
  desktop build. Non-Windows and scripted use is served by the CLI mode
  (headless, Qt-free, reuses `app/core/` directly) rather than by porting
  and testing the GUI on other platforms.
- **Not trying to out-source-count Subfinder/Amass.** Those tools run
  dozens of generic global passive sources; RadarCL's actual differentiator
  is entity-aware seed discovery — `seed_discoverer.py` detects
  municipality/government/university/company and changes its link-scoring
  table and its search queries accordingly — not raw source volume. A
  curated list of Chilean institutional sources was the other half of this
  claim until v0.4.0, when measuring it returned no addresses and it was
  removed ([ADR-0013](adr/0013-curated-source-stage-removed-after-measurement.md)).

## Competitive positioning

- **Subfinder** (subdomain enumeration, 46+ generic passive sources):
  RadarCL doesn't compete on source count. It competes on doing one
  narrow thing — Chilean email discovery — with entity-aware scoring no
  generic tool does.
- **theHarvester** (broad-scope email/subdomain harvesting, 54+ sources
  including PGP keyservers, multi-format output): the closest OSS analog
  in *purpose*, broader in *scope*. RadarCL's edge is depth on one country
  rather than breadth across all of them, plus a verification stage
  theHarvester doesn't have at all.
- **Hunter.io / RocketReach / Snov.io** (paid SaaS): differentiate on
  pattern-guessing plus real-time verification. RadarCL already does both
  of those, combined, for free and open-source
  ([ADR-0009](adr/0009-mx-resolution-failure-is-unknown.md),
  `pattern_generator.py`) — this combination is the single clearest thing
  worth stating plainly in outward-facing copy rather than leaving implicit.

## Success criteria for v1.0

- The versioned feature line in [ROADMAP.md](../ROADMAP.md) (0.25 through
  1.00) is shipped.
- CI is green on every push/PR (currently no `.github/workflows/`).
- An outside contributor can find CONTRIBUTING.md, open a PR, and have it
  run against the same checks a maintainer would run locally.
- `app/core/` is documented and usable as a standalone import, not just
  discoverable by reading GUI code.

## Constraints

- Must run acceptably on low-spec hardware (old office desktops), per
  [ADR-0005](adr/0005-hardware-aware-auto-tuning.md) — any new
  concurrency-heavy feature (e.g. distributed crawling) needs to revisit
  that ADR's tiering assumptions, not silently bypass them.
- Session data is treated as sensitive and non-permanent by design
  ([ADR-0006](adr/0006-sqlite-session-store-last-10-pruning.md)) —
  new persistence needs (e.g. CLI-mode output, distributed job state)
  should inherit that stance rather than introducing unbounded storage.
- Responsible-use framing (README's "Aviso legal / uso responsable")
  applies to every new capability that increases reach or speed
  (distributed crawling, proxy rotation) — this is a project stance, not
  legal advice.
