# RadarCL

Desktop app to discover and verify .cl email addresses from Chilean websites.

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

### v1.0 (current)
- Automatic seed discovery via crt.sh, DNS probing, semantic scoring
- Entity-aware crawling (municipality, government, university, company)
- Live terminal email feed
- Multi-stage verification (syntax, MX, SMTP)
- Auto-export to Desktop CSV
- Hardware-aware performance tuning
- Pause/resume with session state preserved

## Planned Features

### v1.1
- `.com` domain support for Chilean companies with international domains
  (e.g. `@bhp.com`, `@codelco.com`)
- Pattern-based email generation for undisclosed addresses
- Cloud-based crawling to bypass IP blocks