"""
Email extractor.

Pulls .cl email addresses from HTML via:
  - mailto: links
  - regex over visible text
  - obfuscated patterns (e.g. user [at] domain.cl)
"""

import re
from bs4 import BeautifulSoup


_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.cl\b',
    re.IGNORECASE
)

_OBFUSCATED_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+\s*(?:\[at\]|\(at\)|\s+at\s+)\s*[a-zA-Z0-9.\-]+\.cl\b',
    re.IGNORECASE
)


def extract_emails(html: str, source_url: str) -> list[dict]:
    """
    Extract .cl email addresses from an HTML page.

    Parameters
    ----------
    html : str
        Raw HTML content of the page.
    source_url : str
        URL the page was fetched from, stored with each result.

    Returns
    -------
    list[dict]
        Each dict has keys: 'email' (str, lowercase), 'source' (str).
    """
    soup = BeautifulSoup(html, 'lxml')
    found: set[str] = set()

    # mailto: links
    for tag in soup.find_all('a', href=True):
        href = tag['href']
        if href.lower().startswith('mailto:'):
            addr = href[7:].split('?')[0].strip().lower()
            if _EMAIL_RE.match(addr):
                found.add(addr)

    # Regex over visible text
    text = soup.get_text(separator=' ')
    for match in _EMAIL_RE.finditer(text):
        found.add(match.group().lower())

    # Obfuscated patterns
    for match in _OBFUSCATED_RE.finditer(text):
        normalised = re.sub(
            r'\s*(?:\[at\]|\(at\)|\s+at\s+)\s*',
            '@',
            match.group(),
            flags=re.IGNORECASE
        ).lower()
        if _EMAIL_RE.match(normalised):
            found.add(normalised)

    return [{'email': e, 'source': source_url} for e in found]