"""
One rule for what is in scope, replacing five hardcoded `.cl` checks.

Scope follows the target ([ADR-0024](../../docs/adr/0024-scope-follows-the-target-domain.md)):
name a target domain and an address at that domain is in scope whatever its
TLD; name none and scope is `.cl`, which is what every scan did before.

The five copies this replaces each produced silence rather than a refusal -
the extractor could not match `@bhp.com`, the verifier called it malformed,
generation skipped it, the crawler discarded every link on it, and the
search-result regex captured no URL for it. A single rule is the point:
the next target on a TLD nobody anticipated costs no decision at all.

Qt-free, and imported by `extractor`, `verifier`, `crawler`, `pipeline` and
`seed_discoverer` alike, so it may import none of them.
"""

import re
from functools import lru_cache
from urllib.parse import urlparse


_LOCAL = r'[a-zA-Z0-9._%+\-]+'
_CL_HOST = r'[a-zA-Z0-9.\-]+\.cl'
_SUBDOMAINS = r'(?:[a-zA-Z0-9\-]+\.)*'


def normalise(target: str | None) -> str:
    """
    Return a bare lowercase target domain.

    Parameters
    ----------
    target : str | None
        A domain with or without a leading '@', or nothing.

    Returns
    -------
    str
        Empty when no target was named, which is a real answer meaning
        `.cl` scope rather than an absent one.
    """
    return target.strip().lstrip('@').lower() if target else ''


def is_cl(host: str) -> bool:
    """True if a hostname or email domain sits under the `.cl` ccTLD."""
    parts = host.split('.')
    return len(parts) >= 2 and parts[-1] == 'cl'


def covers(domain: str, target: str) -> bool:
    """
    True if `domain` is `target` or a subdomain of it.

    A bare `endswith` would let `notnunoa.cl` answer for a `nunoa.cl`
    target, which is how a stranger's address reaches a file labelled as
    someone's contacts.

    Parameters
    ----------
    domain : str
        Lowercase hostname or email domain.
    target : str
        Bare lowercase target domain.
    """
    if not domain or not target:
        return False
    return domain == target or domain.endswith(f'.{target}')


def domain_of(email: str) -> str:
    """Return the lowercase domain part of an address, '' if there is none."""
    local, at, domain = email.rpartition('@')
    return domain.lower() if at and local else ''


def in_scope(email: str, target: str = '') -> bool:
    """
    True if an address belongs to the named target, or to `.cl` if none.

    Parameters
    ----------
    email : str
    target : str
        Bare lowercase target domain, '' for `.cl` scope.
    """
    domain = domain_of(email)
    if not domain:
        return False
    return covers(domain, target) if target else is_cl(domain)


def host_in_scope(url: str, target: str = '') -> bool:
    """
    True if a URL's host may be followed during phase 1 of a crawl.

    Widening this past `.cl` is what makes a non-`.cl` scan work at all.
    Without it a `bhp.com` seed is fetched, every link on it is discarded
    for being off-`.cl`, the frontier empties, and the crawl ends at the
    seeds having read one page.

    `.cl` stays in scope even when a target is named, so a Chilean site
    linked from the target is still crawled; the address filter in
    `pipeline` is what narrows results to the target itself.
    """
    host = urlparse(url).netloc.lower().split(':')[0]
    if not host:
        return False
    return is_cl(host) or covers(host, target)


def _hosts(target: str) -> str:
    """Regex alternation matching a `.cl` host or the target and its subdomains."""
    if not target:
        return _CL_HOST
    return f'(?:{_CL_HOST}|{_SUBDOMAINS}{re.escape(target)})'


@lru_cache(maxsize=64)
def email_re(target: str = '') -> re.Pattern:
    """Match an in-scope address in free text."""
    return re.compile(rf'{_LOCAL}@{_hosts(target)}\b', re.IGNORECASE)


@lru_cache(maxsize=64)
def obfuscated_re(target: str = '') -> re.Pattern:
    """Match a `user [at] domain` rendering of an in-scope address."""
    return re.compile(
        rf'{_LOCAL}\s*(?:\[at\]|\(at\)|\s+at\s+)\s*{_hosts(target)}\b',
        re.IGNORECASE,
    )


@lru_cache(maxsize=64)
def url_re(target: str = '') -> re.Pattern:
    """Match an in-scope URL inside a search-results page."""
    return re.compile(rf'https?://{_hosts(target)}[^\s"<>]*', re.IGNORECASE)
