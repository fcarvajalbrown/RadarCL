"""
Unit tests for MX resolution with fallback transports.

All offline: every transport is replaced with a stub. Run with:
    pytest tests/test_dns_lookup.py -v
"""

import pytest

from app.core import dns_lookup
from app.core.dns_lookup import DomainNotFound, MXUnavailable, resolve_mx


def _fail(message: str):
    """Build a transport stub that reports a transient failure."""
    def _transport(domain: str) -> str:
        raise MXUnavailable(message)
    return _transport


def _succeed(host: str):
    """Build a transport stub that resolves successfully."""
    def _transport(domain: str) -> str:
        return host
    return _transport


def _patch_chain(monkeypatch, system, public, doh) -> None:
    """Replace the three transports resolve_mx tries in order."""
    monkeypatch.setattr(dns_lookup, '_system_lookup', system)
    monkeypatch.setattr(dns_lookup, '_public_lookup', public)
    monkeypatch.setattr(dns_lookup, '_doh_lookup', doh)


def test_system_resolver_used_first(monkeypatch) -> None:
    """When the system resolver answers, no fallback is attempted."""
    def _boom(domain):
        raise AssertionError("fallback must not run")

    _patch_chain(monkeypatch, _succeed('mx.system.cl'), _boom, _boom)
    assert resolve_mx('nunoa.cl') == 'mx.system.cl'


def test_falls_back_to_public_nameservers(monkeypatch) -> None:
    """A system-resolver timeout falls through to public nameservers."""
    def _boom(domain):
        raise AssertionError("DoH must not run")

    _patch_chain(
        monkeypatch, _fail('LifetimeTimeout'), _succeed('mx.public.cl'), _boom
    )
    assert resolve_mx('nunoa.cl') == 'mx.public.cl'


def test_falls_back_to_doh(monkeypatch) -> None:
    """
    With UDP/53 unreachable, DNS-over-HTTPS still resolves.

    This is the case that produced the bug: dnspython times out against the
    configured nameservers while ordinary HTTPS works fine.
    """
    _patch_chain(
        monkeypatch,
        _fail('LifetimeTimeout'),
        _fail('LifetimeTimeout'),
        _succeed('aspmx.l.google.com'),
    )
    assert resolve_mx('nunoa.cl') == 'aspmx.l.google.com'


def test_all_transports_failing_raises_mx_unavailable(monkeypatch) -> None:
    """Exhausting every transport is indeterminate, never a verdict."""
    _patch_chain(
        monkeypatch, _fail('sys down'), _fail('public down'), _fail('doh down')
    )
    with pytest.raises(MXUnavailable) as exc:
        resolve_mx('nunoa.cl')

    # The combined message keeps each transport's reason for diagnosis.
    assert 'sys down' in str(exc.value)
    assert 'doh down' in str(exc.value)


def test_nonexistent_domain_short_circuits(monkeypatch) -> None:
    """
    NXDOMAIN is definitive, so no fallback is tried.

    A domain that does not exist cannot be rescued by a second resolver,
    and retrying would only slow the verdict down.
    """
    def _nxdomain(domain):
        raise DomainNotFound(f'{domain} does not exist')

    def _boom(domain):
        raise AssertionError("no fallback after NXDOMAIN")

    _patch_chain(monkeypatch, _nxdomain, _boom, _boom)
    with pytest.raises(DomainNotFound):
        resolve_mx('thisdoesnotexist123456.cl')


def test_doh_parses_lowest_preference_record(monkeypatch) -> None:
    """The DoH transport picks the lowest-preference MX host."""
    class _Response:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {
                'Status': 0,
                'Answer': [
                    {'type': 15, 'data': '40 aspmx2.googlemail.com.'},
                    {'type': 15, 'data': '10 aspmx.l.google.com.'},
                    {'type': 15, 'data': '20 alt1.aspmx.l.google.com.'},
                ],
            }

    monkeypatch.setattr(dns_lookup.httpx, 'get', lambda *a, **k: _Response())
    assert dns_lookup._doh_lookup('nunoa.cl') == 'aspmx.l.google.com'


def test_doh_reports_nxdomain(monkeypatch) -> None:
    """DoH status 3 is NXDOMAIN, a definitive negative."""
    class _Response:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {'Status': 3}

    monkeypatch.setattr(dns_lookup.httpx, 'get', lambda *a, **k: _Response())
    with pytest.raises(DomainNotFound):
        dns_lookup._doh_lookup('thisdoesnotexist123456.cl')
