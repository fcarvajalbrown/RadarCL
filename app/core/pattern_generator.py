"""
Email pattern generator.

Harvests person names from HTML pages and generates candidate
email addresses using a user-supplied pattern template.

Supported tokens:
  {first}  — full first name   (felipe)
  {last}   — full last name    (carvajal)
  {f}      — first initial     (f)
  {l}      — last initial      (c)

Examples:
  {first}.{last}  →  felipe.carvajal@bhp.cl
  {f}{last}       →  fcarvajal@bhp.cl
  {first}_{last}  →  felipe_carvajal@bhp.cl
  {f}.{last}      →  f.carvajal@bhp.cl

Common Chilean corporate patterns are provided as presets
for quick selection in the UI.
"""

import re
from bs4 import BeautifulSoup


# Common patterns offered as presets in the UI dropdown
COMMON_PATTERNS: list[dict] = [
    {"label": "felipe.carvajal",  "pattern": "{first}.{last}"},
    {"label": "fcarvajal",        "pattern": "{f}{last}"},
    {"label": "f.carvajal",       "pattern": "{f}.{last}"},
    {"label": "felipe_carvajal",  "pattern": "{first}_{last}"},
    {"label": "carvajal.felipe",  "pattern": "{last}.{first}"},
    {"label": "carvajalf",        "pattern": "{last}{f}"},
    {"label": "felipe",           "pattern": "{first}"},
]

# Regex to detect likely person names: two or more capitalised words
# Intentionally conservative to avoid generating junk candidates.
_NAME_RE = re.compile(
    r'\b([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,})\s+([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]{2,})\b'
)

# Chilean common first names to help disambiguate name order
# (partial list — enough to improve heuristic accuracy)
_CL_FIRST_NAMES: set[str] = {
    "Felipe", "Rodrigo", "Carlos", "Jorge", "Andrés", "Diego", "Luis",
    "Pablo", "Mario", "Francisco", "Alejandro", "Cristián", "Sebastián",
    "Claudio", "Ricardo", "Eduardo", "Gonzalo", "Marcelo", "Patricio",
    "Ignacio", "Tomás", "Nicolás", "Matías", "Bastián", "Javier",
    "María", "Ana", "Claudia", "Paula", "Carolina", "Andrea", "Verónica",
    "Gabriela", "Patricia", "Lorena", "Valeria", "Daniela", "Camila",
    "Javiera", "Francisca", "Catalina", "Isadora", "Constanza", "Sofía",
}


def _normalise(name: str) -> str:
    """
    Normalise a name token for use in an email address.

    Removes accents, lowercases, strips non-alpha characters.

    Parameters
    ----------
    name : str

    Returns
    -------
    str
    """
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ü': 'u', 'ñ': 'n', 'Á': 'a', 'É': 'e', 'Í': 'i',
        'Ó': 'o', 'Ú': 'u', 'Ü': 'u', 'Ñ': 'n',
    }
    result = name.lower()
    for accented, plain in replacements.items():
        result = result.replace(accented, plain)
    return re.sub(r'[^a-z]', '', result)


def _apply_pattern(first: str, last: str, pattern: str) -> str:
    """
    Apply a pattern template to a first/last name pair.

    Parameters
    ----------
    first : str
        Normalised first name.
    last : str
        Normalised last name.
    pattern : str
        Pattern template with tokens.

    Returns
    -------
    str
        Formatted local part of the email address.
    """
    return (
        pattern
        .replace('{first}', first)
        .replace('{last}',  last)
        .replace('{f}',     first[0] if first else '')
        .replace('{l}',     last[0]  if last  else '')
    )


def harvest_names(html: str) -> list[tuple[str, str]]:
    """
    Extract likely person name pairs from an HTML page.

    Uses a conservative regex over visible text and a heuristic
    to determine which token is the first name vs last name.

    Parameters
    ----------
    html : str
        Raw HTML content.

    Returns
    -------
    list[tuple[str, str]]
        List of (first_name, last_name) pairs, raw (not normalised).
    """
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text(separator=' ')
    pairs = []
    seen: set[tuple[str, str]] = set()

    for match in _NAME_RE.finditer(text):
        word1, word2 = match.group(1), match.group(2)

        # Heuristic: if word1 is a known first name, assign accordingly
        if word1 in _CL_FIRST_NAMES:
            first, last = word1, word2
        elif word2 in _CL_FIRST_NAMES:
            first, last = word2, word1
        else:
            # Default: assume Western order (first last)
            first, last = word1, word2

        pair = (first, last)
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)

    return pairs


def generate_candidates(
    html: str,
    pattern: str,
    target_domain: str,
) -> list[str]:
    """
    Generate candidate email addresses from names found in HTML.

    Parameters
    ----------
    html : str
        Raw HTML content of the page.
    pattern : str
        Pattern template (e.g. '{first}.{last}').
    target_domain : str
        Email domain without @ (e.g. 'bhp.cl').

    Returns
    -------
    list[str]
        Candidate email addresses (lowercase, deduplicated).
    """
    domain = target_domain.lstrip('@').lower()
    candidates: list[str] = []
    seen: set[str] = set()

    for first_raw, last_raw in harvest_names(html):
        first = _normalise(first_raw)
        last = _normalise(last_raw)

        if not first or not last:
            continue

        local = _apply_pattern(first, last, pattern)
        if not local:
            continue

        email = f"{local}@{domain}"
        if email not in seen:
            seen.add(email)
            candidates.append(email)

    return candidates