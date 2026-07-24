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
