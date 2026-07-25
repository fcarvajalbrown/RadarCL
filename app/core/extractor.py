"""
Email extractor.

Pulls .cl email addresses from HTML via:
  - mailto: links
  - regex over visible text
  - obfuscated patterns (e.g. user [at] domain.cl)

Each result says whether it was found **only** inside markup hidden from a
reader. Those are spam traps far more often than they are contacts: an
address planted in a `display:none` div, in white-on-white text or behind a
`font-size:0` link is placed exactly where a harvester will find it and a
person will not. It has never belonged to anyone, and mail sent to one is
grounds for a Spamhaus listing that poisons the sender's whole domain.

The flag is not a filter here. `pipeline` carries it through and
`exporter` keeps such addresses out of the CSV, which ADR-0010 defines as
the mailable list, while leaving them in the JSON and HTML run record -
the same split ADR-0016 draws for catch-all domains.
"""

import re
from bs4 import BeautifulSoup, Tag


_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.cl\b',
    re.IGNORECASE
)

_OBFUSCATED_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+\s*(?:\[at\]|\(at\)|\s+at\s+)\s*[a-zA-Z0-9.\-]+\.cl\b',
    re.IGNORECASE
)

# Inline styles that put content out of a reader's reach. Each of these is a
# documented honeypot placement rather than a guess at what might hide
# something: form-field traps are hidden with exactly these declarations.
_HIDDEN_STYLE_RE = re.compile(
    r'display\s*:\s*none'
    r'|visibility\s*:\s*hidden'
    r'|opacity\s*:\s*0(?!\s*\.)(?!\d)'
    r'|font-size\s*:\s*0(?!\.[1-9])(?!\d)'
    r'|(?:width|height)\s*:\s*0(?:px)?\s*(?:;|$)'
    r'|text-indent\s*:\s*-\s*\d{3,}',
    re.IGNORECASE,
)

# Colour declarations, used to catch text painted the same shade as the
# surface behind it. Only the same-element case is detected: a page that
# sets the background on a parent and the colour on a child is not caught,
# and pretending otherwise would need a CSS cascade this does not have.
_COLOUR_RE = re.compile(
    r'(?<!-)\bcolor\s*:\s*([#\w(),.\s%]+?)\s*(?:;|$)', re.IGNORECASE
)
_BACKGROUND_RE = re.compile(
    r'\bbackground(?:-color)?\s*:\s*([#\w(),.\s%]+?)\s*(?:;|$)', re.IGNORECASE
)

# Shades treated as equal when comparing text against its background, so
# `#fff` and `#ffffff` and `white` are one colour.
_COLOUR_ALIASES = {
    '#fff': 'white', '#ffffff': 'white', 'white': 'white',
    '#000': 'black', '#000000': 'black', 'black': 'black',
}


# Cloudflare's Scrape Shield rewrites addresses two ways: an anchor to
# `/cdn-cgi/l/email-protection#<hex>`, and an inline
# `<span class="__cf_email__" data-cfemail="<hex>">`. Both carry the same
# payload.
_CF_PAYLOAD_RE = re.compile(
    r'(?:data-cfemail\s*=\s*["\']|/cdn-cgi/l/email-protection\#)([0-9a-fA-F]{4,})',
)


def find_cf_payloads(html: str) -> list[str]:
    """Every Cloudflare-obfuscated payload in a page, as hex strings."""
    return _CF_PAYLOAD_RE.findall(html or '')


def decode_cf_email(payload: str) -> str | None:
    """
    Decode one Cloudflare payload.

    Single-byte XOR whose key is the first octet of the ciphertext, so the
    key travels with the message. Cloudflare does not present this as
    encryption: its purpose is to be enough to defeat a script that only
    looks for `mailto:`, which is what this extractor was.

    Returns None on anything malformed, since a half-decoded address is
    worse than none.

    The payload carries the whole `mailto:` target, so it can include a
    query string: `csdcolocolo.cl` encodes
    `ventas@csdcolocolo.cl?subject=Asistencia...`. Split on `?` exactly as
    the plain `mailto:` branch does, or the address arrives with a subject
    line welded to the domain.
    """
    try:
        key = int(payload[:2], 16)
        decoded = bytes(
            int(payload[i:i + 2], 16) ^ key
            for i in range(2, len(payload) - 1, 2)
        ).decode('utf-8')
    except (ValueError, UnicodeDecodeError):
        return None
    decoded = decoded.split('?')[0].strip()
    return decoded if '@' in decoded else None


def _same_colour_as_background(style: str) -> bool:
    """True if an element paints its text the same shade as its background."""
    colour = _COLOUR_RE.search(style)
    background = _BACKGROUND_RE.search(style)
    if not (colour and background):
        return False
    a = colour.group(1).strip().lower()
    b = background.group(1).strip().lower()
    return _COLOUR_ALIASES.get(a, a) == _COLOUR_ALIASES.get(b, b)


def _is_hidden(tag: Tag) -> bool:
    """
    True if this element is hidden from a reader by its own markup.

    Only the element's own attributes are read. Hiding applied from a
    stylesheet or set by script is invisible here, because resolving that
    needs a CSS engine and a DOM, which is the headless-browser cost this
    crawler deliberately does not pay.
    """
    if tag.has_attr('hidden'):
        return True
    if str(tag.get('aria-hidden', '')).lower() == 'true':
        return True
    if tag.name == 'input' and str(tag.get('type', '')).lower() == 'hidden':
        return True
    style = str(tag.get('style', ''))
    if not style:
        return False
    return bool(_HIDDEN_STYLE_RE.search(style)) or _same_colour_as_background(style)


def _addresses_in(soup: BeautifulSoup | Tag) -> set[str]:
    """Every .cl address reachable in this subtree, by all three routes."""
    found: set[str] = set()

    # `find_all` searches descendants only. When a hidden subtree *is* the
    # anchor - `<a href="mailto:..." style="font-size:0">` - the root is the
    # whole match, so it has to be considered alongside its children.
    anchors = list(soup.find_all('a', href=True))
    if isinstance(soup, Tag) and soup.name == 'a' and soup.has_attr('href'):
        anchors.append(soup)

    for tag in anchors:
        href = tag['href']
        if href.lower().startswith('mailto:'):
            addr = href[7:].split('?')[0].strip().lower()
            if _EMAIL_RE.match(addr):
                found.add(addr)
        elif 'email-protection#' in href.lower():
            # Cloudflare rewrote a mailto into a link to its own decoder.
            decoded = decode_cf_email(href.split('#', 1)[1])
            if decoded and _EMAIL_RE.match(decoded.lower()):
                found.add(decoded.lower())

    # The inline form: a span whose text Cloudflare's own script replaces in
    # the browser. Read off the attribute, so no script has to run.
    cf_spans = list(soup.find_all(attrs={'data-cfemail': True}))
    if isinstance(soup, Tag) and soup.has_attr('data-cfemail'):
        cf_spans.append(soup)
    for tag in cf_spans:
        decoded = decode_cf_email(str(tag['data-cfemail']))
        if decoded and _EMAIL_RE.match(decoded.lower()):
            found.add(decoded.lower())

    text = soup.get_text(separator=' ')
    for match in _EMAIL_RE.finditer(text):
        found.add(match.group().lower())

    for match in _OBFUSCATED_RE.finditer(text):
        normalised = re.sub(
            r'\s*(?:\[at\]|\(at\)|\s+at\s+)\s*',
            '@',
            match.group(),
            flags=re.IGNORECASE
        ).lower()
        if _EMAIL_RE.match(normalised):
            found.add(normalised)

    return found


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
        Each dict has keys: 'email' (str, lowercase), 'source' (str), and
        'hidden' (bool). `hidden` is True only when every occurrence of
        that address on the page was inside markup a reader cannot see. An
        address that appears both in a contact block and in a hidden div is
        not a trap, so it is reported as visible.
    """
    soup = BeautifulSoup(html, 'lxml')

    # Pull the hidden subtrees out of the document, so what remains is what
    # a reader would have seen. Detached rather than discarded: the
    # addresses inside them are still reported, marked.
    hidden_trees = [
        tag.extract() for tag in soup.find_all(_is_hidden)
        if tag.parent is not None
    ]

    visible = _addresses_in(soup)
    hidden: set[str] = set()
    for tree in hidden_trees:
        hidden |= _addresses_in(tree)

    return (
        [{'email': e, 'source': source_url, 'hidden': False}
         for e in visible]
        + [{'email': e, 'source': source_url, 'hidden': True}
           for e in sorted(hidden - visible)]
    )
