"""
Evidence that the page an address was found on is Chilean.

This module never decides what gets collected. It annotates. A `.com`
address carries no country at all, so the only thing that can carry one is
the page it was scraped from, and even that only sometimes - see
[ADR-0014](../../docs/adr/0014-country-is-never-inferred-from-a-com-address.md).

`chile_evidence` returns the names of the signals that fired, so a caller
can show a user what the claim rests on rather than a number that hides it.
An empty result means no evidence was found, which is not the same as
evidence the page is foreign.

The claim each signal makes is about the *page*, never about who owns the
company. `teck.com` fires `phone-cl` because its contact page lists a
Santiago office and a real Chilean landline; Teck is Canadian, and the
signal is still correct, because it says the page carries Chilean evidence
and nothing more. Callers must not relabel that as a nationality.

Every signal left out was left out on a measurement, not on taste:
place-name counting and a comuna gazetteer cannot separate a passing
mention of Chile from an actual Chilean office, a resolving sibling `.cl`
was 56% wrong and is not a fact about the page anyway, `hreflang="es-CL"`
fired only on a US company, and no corporate homepage in the sample
published JSON-LD `addressCountry` at all.

Nothing here may import Qt - see the layering rule in CLAUDE.md.
"""

import re
import unicodedata
from urllib.parse import urlparse

import phonenumbers
from bs4 import BeautifulSoup
from stdnum.cl import rut as cl_rut


# RUT-shaped candidates, validated afterwards by stdnum. The check digit is
# what makes this an assertion rather than a pattern match: a random
# eight-digit number formatted as a RUT fails.
_RUT_CANDIDATE = re.compile(
    r'\b(?:\d{1,2}(?:\.\d{3}){2}|\d{7,8})-[\dkK]\b'
)

# Chilean institutional vocabulary, not place names. `Chile` and `Santiago`
# appear on any multinational miner's page; `casilla` and `fono` do not.
_LEXICON = (
    'rut', 'comuna', 'fono', 'casilla', 'giro', 'clp', 'pesos chilenos',
    'region metropolitana', 'servicio de impuestos internos',
    'sociedad por acciones',
)

# A country-scoped path segment: `/falabella-cl`, `/es/chile`, `/cl/`.
_PATH_SEGMENT = re.compile(r'^(?:cl|chile|es-cl)$|-cl$', re.IGNORECASE)

# A US ZIP+4 is nine digits, and one beginning with 9 parses as a valid
# Chilean mobile: `teck.com` lists `Spokane, WA 99201-0301`, which
# libphonenumber accepts as `+56 9 9201 0301`. Leniency does not help -
# STRICT_GROUPING keeps this and discards real numbers written `22 818 5000`.
# ponytail: covers the one collision class measured; other nine-digit codes
# printed with a 5-4 split would still slip through.
_ZIP_PLUS_FOUR = re.compile(r'^\d{5}-\d{4}$')


def _deaccent(text: str) -> str:
    """Return `text` with combining accents stripped, for robust matching."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def _has_valid_rut(text: str) -> bool:
    """True if `text` contains at least one RUT with a valid check digit."""
    return any(
        cl_rut.is_valid(m.group()) for m in _RUT_CANDIDATE.finditer(text)
    )


def _has_cl_phone(text: str) -> bool:
    """
    True if `text` contains a valid Chilean phone number.

    Parsed with `CL` as the default region, so numbers written the way
    Chilean sites actually write them - `22 818 5000`, no `+56` - are
    matched too. The region of each match is checked afterwards, so a
    number carrying an explicit foreign country code is rejected rather
    than reinterpreted as Chilean.
    """
    for match in phonenumbers.PhoneNumberMatcher(text, 'CL'):
        if phonenumbers.region_code_for_number(match.number) != 'CL':
            continue
        if _ZIP_PLUS_FOUR.match(match.raw_string.strip()):
            continue
        return True
    return False


def chile_evidence(html: str, source_url: str) -> tuple[str, ...]:
    """
    Return the names of the Chilean-evidence signals present on a page.

    Parameters
    ----------
    html : str
        Raw HTML of the page an address was found on.
    source_url : str
        URL the page was fetched from, after redirects.

    Returns
    -------
    tuple[str, ...]
        Sorted signal names, from: 'lang-es-cl', 'lexicon', 'path-cl',
        'phone-cl', 'rut'. Empty if nothing fired, which means no evidence
        was found rather than that the page is foreign.
    """
    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text(separator=' ')
    lowered = _deaccent(text.lower())

    found: set[str] = set()

    lang = (soup.html.get('lang') if soup.html else None) or ''
    if lang.strip().lower().replace('_', '-') == 'es-cl':
        found.add('lang-es-cl')

    if _has_valid_rut(text):
        found.add('rut')

    if _has_cl_phone(text):
        found.add('phone-cl')

    if any(re.search(rf'\b{re.escape(word)}\b', lowered) for word in _LEXICON):
        found.add('lexicon')

    path = urlparse(source_url).path
    if any(_PATH_SEGMENT.search(seg) for seg in path.split('/') if seg):
        found.add('path-cl')

    return tuple(sorted(found))
