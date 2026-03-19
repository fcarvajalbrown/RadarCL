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