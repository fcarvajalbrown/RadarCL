"""
Measure what a PGP keyserver recovers per request for `.cl` domains.

Instrumentation for [docs/research/pgp-keyserver-yield.md]. The frame, the
seed, the sample size and the ship gate were committed before this ran.

Two keyservers still answer a domain search: keyserver.ubuntu.com and
pgp.mit.edu. keys.openpgp.org refuses by policy, so it is not queried.

Stage 1 collects addresses. Stage 2 verifies a random subsample through
`app.core.verifier.verify`, because the gate is live addresses per request
and a keyserver full of 1990s academic addresses would pass a raw count.

Usage
-----
    python -m scripts.pgp_keyserver_yield --input scripts/data/pgp_cl.txt
    python -m scripts.pgp_keyserver_yield --input <file> --verify 60
"""

import argparse
import csv
import math
import random
import re
import sys
import time
from pathlib import Path

import httpx

from app.core.seed_discoverer import detect_entity_type
from app.core.verifier import VStatus, verify

USER_AGENT = 'Mozilla/5.0 (compatible; RadarCL-research/0.5.5)'

KEYSERVERS = {
    'ubuntu': 'https://keyserver.ubuntu.com/pks/lookup',
    'mit': 'https://pgp.mit.edu/pks/lookup',
}

# HKP index pages are HTML tables of UIDs; the addresses are plain text in
# them. Anchored to the target domain so a key carrying several UIDs
# contributes only the ones actually under that domain.
def _address_re(domain: str) -> re.Pattern:
    return re.compile(
        rf'[a-zA-Z0-9._%+\-]+@(?:[a-zA-Z0-9\-]+\.)*{re.escape(domain)}\b',
        re.IGNORECASE,
    )


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval, as used throughout these measurements."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - m), min(1.0, c + m))


def query(server: str, domain: str, delay: float) -> tuple[set[str], str]:
    """
    Ask one keyserver for every key whose UID is under `domain`.

    Returns the addresses found and an outcome string. A request that
    errors is reported as non-response rather than as an empty result: a
    keyserver that did not answer has not told us the domain has no keys.
    """
    try:
        response = httpx.get(
            KEYSERVERS[server],
            params={'search': f'@{domain}', 'op': 'index'},
            headers={'User-Agent': USER_AGENT},
            timeout=60.0,
            follow_redirects=True,
        )
    except Exception as exc:
        return set(), f'error: {type(exc).__name__}'
    finally:
        time.sleep(delay)

    if response.status_code == 404:
        # HKP says 404 for "no keys found", which is an answer.
        return set(), 'none'
    if response.status_code != 200:
        return set(), f'http {response.status_code}'

    found = {m.group(0).lower() for m in _address_re(domain).finditer(response.text)}
    return found, 'ok'


def collect(domains: list[str], delay: float) -> tuple[list[dict], dict]:
    """Query both keyservers for every domain."""
    rows: list[dict] = []
    requests = 0
    for index, domain in enumerate(domains, 1):
        entity = detect_entity_type(domain)
        per_server: dict[str, set[str]] = {}
        for server in KEYSERVERS:
            found, outcome = query(server, domain, delay)
            requests += 1
            per_server[server] = found
            rows.append({
                'domain': domain,
                'entity': entity.name.lower(),
                'server': server,
                'outcome': outcome,
                'count': len(found),
                'addresses': ' '.join(sorted(found)),
            })
        union = set().union(*per_server.values())
        print(f'  {index}/{len(domains)} {domain:34s} '
              f'ubuntu={len(per_server["ubuntu"]):3d} '
              f'mit={len(per_server["mit"]):3d} union={len(union)}',
              file=sys.stderr)
    return rows, {'requests': requests}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='pgp_keyserver_yield')
    parser.add_argument('--input', required=True)
    parser.add_argument('--out', default=None)
    parser.add_argument('--verify', type=int, default=60,
                        help='How many recovered addresses to verify. 0 skips.')
    parser.add_argument('--seed', type=int, default=20260726)
    parser.add_argument('--delay', type=float, default=1.5,
                        help="Seconds between requests. Somebody else's server.")
    args = parser.parse_args(argv)

    domains = [
        line.strip() for line in
        Path(args.input).read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('#')
    ]
    print(f'{len(domains)} domains from {args.input}', file=sys.stderr)

    rows, stats = collect(domains, args.delay)

    if args.out:
        with open(args.out, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=['domain', 'entity', 'server', 'outcome', 'count',
                            'addresses'],
            )
            writer.writeheader()
            writer.writerows(rows)

    # --- yield -------------------------------------------------------
    by_domain: dict[str, set[str]] = {}
    for row in rows:
        by_domain.setdefault(row['domain'], set()).update(
            row['addresses'].split() if row['addresses'] else []
        )
    every = sorted(set().union(*by_domain.values())) if by_domain else []
    answered = sum(1 for r in rows if r['outcome'] in ('ok', 'none'))
    nonresponse = len(rows) - answered

    print(f'\n  requests issued      {stats["requests"]}')
    print(f'  answered             {answered}')
    print(f'  non-response         {nonresponse}')
    print(f'  domains with keys    '
          f'{sum(1 for d in by_domain.values() if d)}/{len(by_domain)}')
    print(f'  distinct addresses   {len(every)}')
    print(f'  raw per request      {len(every) / max(1, answered):.2f}')

    for server in KEYSERVERS:
        sub = [r for r in rows if r['server'] == server]
        got = set()
        for r in sub:
            got.update(r['addresses'].split() if r['addresses'] else [])
        print(f'    {server:8s} {len(got):5d} addresses, '
              f'{sum(1 for r in sub if r["outcome"] not in ("ok", "none"))} failed')

    print('\n  by entity type')
    ents: dict[str, list[int]] = {}
    for domain, addrs in by_domain.items():
        ent = next(r['entity'] for r in rows if r['domain'] == domain)
        ents.setdefault(ent, []).append(len(addrs))
    for ent, counts in sorted(ents.items()):
        with_keys = sum(1 for c in counts if c)
        print(f'    {ent:14s} {len(counts):3d} domains, {with_keys:3d} with keys, '
              f'{sum(counts):5d} addresses')

    # --- liveness ----------------------------------------------------
    if not args.verify or not every:
        return 0

    subsample = sorted(random.Random(args.seed).sample(
        every, min(args.verify, len(every))
    ))
    print(f'\n  verifying {len(subsample)} of {len(every)} addresses', file=sys.stderr)

    catch_all_cache: dict[str, bool] = {}
    verdicts: list[str] = []
    for index, address in enumerate(subsample, 1):
        result = verify(address, smtp_enabled=True, catch_all_cache=catch_all_cache)
        verdicts.append(result.status.name)
        print(f'    {index}/{len(subsample)} {address:44s} {result.status.name}',
              file=sys.stderr)
        time.sleep(args.delay)

    # ADR-0009: UNKNOWN is not evidence the mailbox is dead, so it counts
    # as live. Only a definitive INVALID does not.
    dead = sum(1 for v in verdicts if v == VStatus.INVALID.name)
    live = len(verdicts) - dead
    lo, hi = wilson(live, len(verdicts))

    print(f'\n  live {live}/{len(verdicts)} = {live / len(verdicts):.1%}  '
          f'95% Wilson [{lo:.1%}, {hi:.1%}]')
    for name in ('VALID', 'CATCH_ALL', 'UNKNOWN', 'INVALID'):
        print(f'    {name:10s} {verdicts.count(name)}')

    per_request = len(every) / max(1, answered)
    print(f'\n  PRE-REGISTERED GATE: live addresses per request >= 0.65')
    print(f'    point    {per_request * (live / len(verdicts)):.2f}')
    print(f'    interval [{per_request * lo:.2f}, {per_request * hi:.2f}]')
    print(f'    lower bound '
          f'{"CLEARS" if per_request * lo >= 0.65 else "MISSES"} the gate')
    return 0


if __name__ == '__main__':
    sys.exit(main())
