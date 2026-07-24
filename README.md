<div align="center">
<img src="assets/icon.svg" width="120" alt="RadarCL logo: async crawler and verifier for discovering public .cl (Chile) email contacts">

# RadarCL

![version](https://img.shields.io/badge/version-0.2.0-blue)
![license](https://img.shields.io/badge/license-Apache%202.0-green)
![platform](https://img.shields.io/badge/platform-Windows-slate)
![stack](https://img.shields.io/badge/stack-Python%20%7C%20PySide6-blue)
</div>

Async crawler and multi-stage verifier for discovering public email
contacts on Chilean (`.cl`) websites. It automates the pipeline OSINT and
civic-tech tooling usually has to hand-roll for this domain: entity-aware
seed discovery (Certificate Transparency logs via crt.sh, DNS liveness
checks, semantic link scoring, and known high-value Chilean sources), a
phase-based crawler that stays `.cl`-scoped by default, email extraction
with de-obfuscation, and staged verification (syntax → MX → SMTP).

Ships as a PySide6 desktop app for non-technical users, but `app/core/` is
plain Python/asyncio with zero Qt dependency and can be reused standalone —
see `CLAUDE.md` for the architecture split.

## Setup
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
```

## Stack
- GUI: PySide6 (Qt6)
- HTTP: httpx + BeautifulSoup4
- Verification: dnspython + smtplib
- Storage: SQLite (stdlib)
- Packaging: PyInstaller + Nuitka

## Version History

### v0.2.0 (current)
- Automatic seed discovery via crt.sh, DNS probing, semantic scoring
- Entity-aware crawling (municipality, government, university, company)
- Live terminal email feed
- Multi-stage verification (syntax, MX, SMTP)
- Auto-export to Desktop CSV
- Hardware-aware performance tuning
- Pause/resume with session state preserved

## Roadmap

Forward-looking plans live in [ROADMAP.md](ROADMAP.md), with design
decisions recorded in [docs/adr/](docs/adr/).