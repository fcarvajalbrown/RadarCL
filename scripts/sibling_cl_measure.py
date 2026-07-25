"""
Measure how often a non-`.cl` domain has a mail-capable sibling `<base>.cl`.

Instrumentation for [docs/research/sibling-cl-prevalence.md]. The frame,
the seed, the sample size and the ship threshold were committed before
this ran; see that file for all four.

Reuses `app.core.dns_lookup.resolve_mx` rather than reimplementing a
lookup, so the number measured here is what the shipped feature would
actually see, including its three-transport fallback chain.

No SMTP in the sibling mode: a DNS answer settles the question, and
probing a stranger's mail server for something DNS already told us is
traffic sent for nothing.

Usage
-----
    python -m scripts.sibling_cl_measure --input scripts/data/sample_a.txt
    python -m scripts.sibling_cl_measure --input <file> --out results.csv
    python -m scripts.sibling_cl_measure --catch-all --input <cl domains>
"""

import argparse
import csv
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from app.core.dns_lookup import DomainNotFound, MXUnavailable, resolve_mx

PSL_URL = 'https://publicsuffix.org/list/public_suffix_list.dat'
PSL_CACHE = Path(__file__).parent / 'data' / 'public_suffix_list.dat'


def load_psl() -> set[str]:
    """
    Public Suffix List rules, cached on disk after the first fetch.

    Needed because the base of a domain is not its first label:
    `antofagasta.co.uk` is one organisation whose base is `antofagasta`,
    and `chile.angloamerican.com` is a subdomain whose base is
    `angloamerican`. Splitting on the first dot gets both wrong.
    """
    if not PSL_CACHE.exists():
        PSL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(PSL_URL, timeout=60) as response:
            PSL_CACHE.write_bytes(response.read())
    return {
        line.strip()
        for line in PSL_CACHE.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('//')
    }


def base_label(host: str, psl: set[str]) -> str | None:
    """
    The registrable label of a host: `bhp` for `www.bhp.com`.

    Returns None when the host *is* a public suffix with nothing
    registered under it, which has no base to speak of.
    """
    parts = host.lower().strip('.').split('.')
    # Longest matching suffix wins, so `co.uk` beats `uk`. Exception rules
    # (`!`) and wildcards (`*`) are not handled: neither appears in any
    # suffix reachable from this sample, and a rule that never fires is a
    # rule that cannot be tested.
    suffix_len = 1
    for i in range(len(parts)):
        if '.'.join(parts[i:]) in psl:
            suffix_len = max(suffix_len, len(parts) - i)
    if suffix_len >= len(parts):
        return None
    return parts[-(suffix_len + 1)]


@dataclass
class Probe:
    """One domain's result."""
    host: str
    sibling: str
    outcome: str      # 'mail-capable' | 'no-mail' | 'unreachable' | 'no-base'
    detail: str
    seconds: float


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """
    95% Wilson score interval for a proportion.

    Wilson rather than the normal approximation because the latter
    misbehaves near 0 and 1, which is exactly where a small census like
    population (b) is likely to land.
    """
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def measure_siblings(hosts: list[str], delay: float) -> list[Probe]:
    """Ask each host's sibling `.cl` whether it accepts mail."""
    psl = load_psl()
    results: list[Probe] = []
    # Sibling domains are deduplicated: two members sharing bhp.com must
    # not put bhp.cl on the wire twice, and must not count twice either.
    asked: dict[str, tuple[str, str, float]] = {}

    for index, host in enumerate(hosts, 1):
        base = base_label(host, psl)
        if base is None:
            results.append(Probe(host, '', 'no-base', 'host is a public suffix', 0.0))
            continue
        sibling = f'{base}.cl'

        if sibling in asked:
            outcome, detail, seconds = asked[sibling]
            results.append(Probe(host, sibling, outcome, detail + ' (cached)', seconds))
            continue

        started = time.monotonic()
        try:
            mx = resolve_mx(sibling)
            outcome, detail = 'mail-capable', mx
        except DomainNotFound as exc:
            outcome, detail = 'no-mail', str(exc)
        except MXUnavailable as exc:
            outcome, detail = 'unreachable', str(exc)
        seconds = time.monotonic() - started

        asked[sibling] = (outcome, detail, seconds)
        results.append(Probe(host, sibling, outcome, detail, seconds))
        print(f'  {index}/{len(hosts)} {sibling}: {outcome}', file=sys.stderr)
        time.sleep(delay)

    return results


def measure_catch_all(domains: list[str], delay: float) -> list[Probe]:
    """
    Ask each `.cl` domain's mail server whether it accepts invented
    recipients.

    Uses `verifier._is_catch_all` directly rather than verifying a real
    address, since the question is a property of the server. That means
    two RCPT commands of invented local parts per domain and no real
    address probed, which is the smaller intrusion of the two.
    """
    import smtplib
    import socket

    from app.core.verifier import _helo_name, _is_catch_all, _open_transaction

    results: list[Probe] = []
    for index, domain in enumerate(domains, 1):
        started = time.monotonic()
        try:
            mx = resolve_mx(domain)
        except (DomainNotFound, MXUnavailable) as exc:
            results.append(Probe(domain, domain, 'unreachable', str(exc),
                                 time.monotonic() - started))
            time.sleep(delay)
            continue
        try:
            with smtplib.SMTP(timeout=15) as smtp:
                smtp.connect(mx, 25)
                _open_transaction(smtp, _helo_name())
                verdict = _is_catch_all(smtp, domain)
            outcome = 'catch-all' if verdict else 'selective'
            detail = mx
        except (smtplib.SMTPException, socket.error, OSError) as exc:
            outcome, detail = 'unreachable', f'{type(exc).__name__}: {exc}'
        seconds = time.monotonic() - started
        results.append(Probe(domain, domain, outcome, detail, seconds))
        print(f'  {index}/{len(domains)} {domain}: {outcome}', file=sys.stderr)
        time.sleep(delay)
    return results


def report(results: list[Probe], positive: str, negative: str) -> None:
    """Print counts, the proportion, its interval, and non-response."""
    counts: dict[str, int] = {}
    for probe in results:
        counts[probe.outcome] = counts.get(probe.outcome, 0) + 1

    # Deduplicated by sibling: one domain asked twice is one observation.
    seen: set[str] = set()
    unique = [p for p in results
              if p.sibling and not (p.sibling in seen or seen.add(p.sibling))]

    yes = sum(1 for p in unique if p.outcome == positive)
    no = sum(1 for p in unique if p.outcome == negative)
    bad = sum(1 for p in unique if p.outcome == 'unreachable')
    answered = yes + no

    print(f'\n  rows                {len(results)}')
    print(f'  distinct domains    {len(unique)}')
    for outcome, count in sorted(counts.items()):
        print(f'    {outcome:16s}  {count}')

    if answered:
        low, high = wilson(yes, answered)
        print(f'\n  {positive}: {yes}/{answered} reachable = '
              f'{yes / answered:.1%}')
        print(f'  95% Wilson interval  [{low:.1%}, {high:.1%}]')
        print(f'  non-response         {bad} '
              f'({bad / max(1, len(unique)):.1%} of domains)')

    timings = sorted(p.seconds for p in unique if p.outcome != 'no-base')
    if timings:
        mid = timings[len(timings) // 2]
        p95 = timings[min(len(timings) - 1, int(len(timings) * 0.95))]
        print(f'  latency  median {mid:.2f}s   p95 {p95:.2f}s')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='sibling_cl_measure')
    parser.add_argument('--input', required=True,
                        help='One host per line; blank lines and # ignored.')
    parser.add_argument('--out', default=None, help='Write per-domain CSV here.')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Seconds between queries. These are other '
                             'people\'s resolvers and mail servers.')
    parser.add_argument('--catch-all', action='store_true',
                        help='Probe .cl domains for catch-all instead.')
    args = parser.parse_args(argv)

    hosts = [
        line.strip() for line in
        Path(args.input).read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('#')
    ]
    print(f'{len(hosts)} hosts from {args.input}', file=sys.stderr)

    if args.catch_all:
        results = measure_catch_all(hosts, args.delay)
        report(results, 'catch-all', 'selective')
    else:
        results = measure_siblings(hosts, args.delay)
        report(results, 'mail-capable', 'no-mail')

    if args.out:
        with open(args.out, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['host', 'sibling', 'outcome', 'detail', 'seconds'])
            for probe in results:
                writer.writerow([probe.host, probe.sibling, probe.outcome,
                                 probe.detail, f'{probe.seconds:.3f}'])
        print(f'\nwrote {args.out}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
