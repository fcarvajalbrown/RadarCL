"""
MX resolution with fallback transports.

Verification has to distinguish two things that a bare DNS failure looks
identical from the outside: a domain that genuinely does not exist, and a
resolver that could not answer. The first is a verdict, the second is not.
This module raises a different exception for each so `verifier.py` can
classify them correctly - see ADR-0009.

It also tries more than one transport. dnspython queries the configured
nameservers directly over UDP port 53, which fails on networks where those
servers are unreachable or the port is filtered, even though ordinary HTTPS
works fine. That combination is exactly what reported real `@nunoa.cl`
addresses as invalid, so DNS-over-HTTPS is the last resort in the chain.
"""

from typing import Callable

import dns.resolver
import httpx


class DomainNotFound(Exception):
    """
    The domain definitively has no mail exchanger.

    Either the domain does not exist (NXDOMAIN), or it exists with neither
    an MX nor an A record. Callers should treat this as INVALID.
    """


class MXUnavailable(Exception):
    """
    MX resolution could not be completed.

    Every transport failed, so nothing is known about the domain. Callers
    should treat this as UNKNOWN, never as INVALID.
    """


# Public resolvers used when the system-configured nameservers do not
# answer: Google and Cloudflare respectively.
_PUBLIC_NAMESERVERS: list[str] = ['8.8.8.8', '1.1.1.1']

# DNS-over-HTTPS endpoint, reachable wherever plain HTTPS is.
_DOH_ENDPOINT = 'https://dns.google/resolve'

# Per-transport budget. Kept short because there are three of them.
_TIMEOUT = 5.0

# DNS record type number for MX, as returned by the DoH JSON API.
_TYPE_MX = 15


def _lowest_preference(hosts: list[tuple[int, str]]) -> str:
    """Return the hostname with the numerically lowest MX preference."""
    return min(hosts)[1]


def _dns_query(domain: str, nameservers: list[str] | None = None) -> str:
    """
    Resolve MX for a domain over UDP/53, optionally via given nameservers.

    Raises
    ------
    DomainNotFound
        NXDOMAIN, or no MX and no A record.
    MXUnavailable
        Timeout, unreachable nameservers, or any other transport failure.
    """
    resolver = dns.resolver.Resolver()
    if nameservers is not None:
        resolver.nameservers = list(nameservers)
    resolver.timeout = _TIMEOUT
    resolver.lifetime = _TIMEOUT

    try:
        answer = resolver.resolve(domain, 'MX')
    except dns.resolver.NXDOMAIN as exc:
        raise DomainNotFound(f"{domain} does not exist") from exc
    except dns.resolver.NoAnswer:
        return _implicit_mx(domain, resolver)
    except Exception as exc:
        raise MXUnavailable(f"{type(exc).__name__}: {exc}") from exc

    return _lowest_preference(
        [(record.preference, str(record.exchange).rstrip('.'))
         for record in answer]
    )


def _implicit_mx(domain: str, resolver: dns.resolver.Resolver) -> str:
    """
    Handle a domain that exists but publishes no MX record.

    RFC 5321 section 5.1 says that when no MX exists, the address record is
    treated as an implicit mail exchanger, so the domain itself is the mail
    host. Only when there is no A record either does the domain definitively
    have nowhere to deliver.
    """
    try:
        resolver.resolve(domain, 'A')
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN) as exc:
        raise DomainNotFound(
            f"{domain} has no MX and no A record"
        ) from exc
    except Exception as exc:
        raise MXUnavailable(f"{type(exc).__name__}: {exc}") from exc

    return domain


def _system_lookup(domain: str) -> str:
    """Resolve MX using the machine's configured nameservers."""
    return _dns_query(domain)


def _public_lookup(domain: str) -> str:
    """Resolve MX using public nameservers, bypassing local configuration."""
    return _dns_query(domain, _PUBLIC_NAMESERVERS)


def _doh_lookup(domain: str) -> str:
    """
    Resolve MX over DNS-over-HTTPS.

    Last resort, and the only transport that works where UDP/53 is filtered
    but HTTPS is not. A domain with no MX record is reported as unavailable
    rather than resolved to its A record: the implicit-MX fallback needs a
    second query, and by the time this transport runs the cheaper paths that
    handle that case have already failed.
    """
    try:
        response = httpx.get(
            _DOH_ENDPOINT,
            params={'name': domain, 'type': 'MX'},
            headers={'accept': 'application/dns-json'},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise MXUnavailable(f"DoH {type(exc).__name__}: {exc}") from exc

    # RCODE 3 is NXDOMAIN.
    if payload.get('Status') == 3:
        raise DomainNotFound(f"{domain} does not exist")

    hosts: list[tuple[int, str]] = []
    for record in payload.get('Answer') or []:
        if record.get('type') != _TYPE_MX:
            continue
        preference, _, host = str(record.get('data', '')).partition(' ')
        if host:
            hosts.append((int(preference), host.strip().rstrip('.')))

    if not hosts:
        raise MXUnavailable(f"DoH returned no MX records for {domain}")

    return _lowest_preference(hosts)


def resolve_mx(domain: str) -> str:
    """
    Return the lowest-preference mail host for a domain.

    Tries the system resolver, then public nameservers, then DNS-over-HTTPS,
    stopping at the first that answers. A definitive negative short-circuits
    the chain, since no second resolver can rescue a domain that does not
    exist.

    Parameters
    ----------
    domain : str
        Bare domain, e.g. 'nunoa.cl'.

    Returns
    -------
    str
        Mail exchanger hostname to hand to the SMTP stage.

    Raises
    ------
    DomainNotFound
        The domain definitively has no mail exchanger.
    MXUnavailable
        No transport could answer. Nothing is known about the domain.
    """
    failures: list[str] = []

    # Ordered cheapest-and-most-local first. Looked up through module
    # globals on each call rather than bound once, so the transports stay
    # individually replaceable in tests.
    transports: tuple[Callable[[str], str], ...] = (
        _system_lookup, _public_lookup, _doh_lookup,
    )

    for transport in transports:
        try:
            return transport(domain)
        except DomainNotFound:
            raise
        except MXUnavailable as exc:
            failures.append(str(exc))

    raise MXUnavailable('; '.join(failures))
