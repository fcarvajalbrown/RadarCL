"""
Measure how often `.cl` sites hide addresses behind Cloudflare.

Instrumentation for [docs/research/cloudflare-email-obfuscation.md]. Frame
and seed were committed before this ran; no threshold is attached, and that
file says why.

One GET per domain, homepage only. Reports prevalence and, separately, how
many `.cl` addresses decoding actually recovers that the current extractor
misses - which is the number the decision turns on, and can be far lower
than prevalence when a page prints the same address in clear as well.

Usage
-----
    python -m scripts.cloudflare_email_prevalence --input scripts/data/cloudflare_cl.txt
"""

import argparse
import csv
import math
import sys
import time
from pathlib import Path

import httpx

from app.core.crawler import USER_AGENT
from app.core.extractor import (
    decode_cf_email,
    extract_emails,
    find_cf_payloads,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='cloudflare_email_prevalence')
    parser.add_argument('--input', required=True)
    parser.add_argument('--out', default=None)
    parser.add_argument('--delay', type=float, default=1.0)
    args = parser.parse_args(argv)

    domains = [
        line.strip() for line in
        Path(args.input).read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('#')
    ]
    print(f'{len(domains)} domains from {args.input}', file=sys.stderr)

    rows: list[dict] = []
    for index, domain in enumerate(domains, 1):
        try:
            response = httpx.get(
                f'https://{domain}/',
                headers={'User-Agent': USER_AGENT},
                timeout=20.0,
                follow_redirects=True,
            )
            status = response.status_code
            html = response.text if status == 200 else ''
            outcome = 'ok' if status == 200 else f'http {status}'
        except Exception as exc:
            html, outcome = '', f'error: {type(exc).__name__}'

        payloads = find_cf_payloads(html) if html else []
        decoded = {
            addr for addr in (decode_cf_email(p) for p in payloads)
            if addr and addr.lower().endswith('.cl')
        }
        already = {
            r['email'] for r in extract_emails(html, domain)
        } if html else set()
        new = decoded - already

        rows.append({
            'domain': domain,
            'outcome': outcome,
            'payloads': len(payloads),
            'decoded_cl': len(decoded),
            'new_addresses': len(new),
            'sample': ' '.join(sorted(new)[:3]),
        })
        print(f'  {index}/{len(domains)} {domain:32s} {outcome:16s} '
              f'payloads={len(payloads):3d} new={len(new)}', file=sys.stderr)
        time.sleep(args.delay)

    answered = [r for r in rows if r['outcome'] == 'ok']
    unreachable = [r for r in rows if r['outcome'] != 'ok']
    using = [r for r in answered if r['payloads']]
    recovering = [r for r in answered if r['new_addresses']]
    total_new = sum(r['new_addresses'] for r in answered)

    lo, hi = wilson(len(using), len(answered))
    rlo, rhi = wilson(len(recovering), len(answered))

    print(f'\n  domains              {len(rows)}')
    print(f'  reachable            {len(answered)}')
    print(f'  unreachable          {len(unreachable)}')
    print(f'\n  use CF obfuscation   {len(using)}/{len(answered)} = '
          f'{len(using) / max(1, len(answered)):.1%}  '
          f'95% Wilson [{lo:.1%}, {hi:.1%}]')
    print(f'  recover new .cl      {len(recovering)}/{len(answered)} = '
          f'{len(recovering) / max(1, len(answered)):.1%}  '
          f'95% Wilson [{rlo:.1%}, {rhi:.1%}]')
    print(f'  addresses recovered  {total_new}')

    if args.out:
        with open(args.out, 'w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f'\nwrote {args.out}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
