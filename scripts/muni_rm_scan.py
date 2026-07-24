"""
Standalone bulk email-discovery scan: all 52 comunas of the Región
Metropolitana de Santiago, plus achm.cl (Asociación Chilena de
Municipalidades).

Reuses app/core/ directly (seed_discoverer, crawler, extractor,
verifier) with no Qt/GUI involved — built for one-off headless runs
across many domains, which the GUI isn't designed to batch.

Verification is syntax + MX only (no live SMTP) to keep runtime
reasonable across 53 domains. Only emails actually found on a page
are included — no pattern-guessed candidates.

Usage
-----
    python -m scripts.muni_rm_scan
    python -m scripts.muni_rm_scan --max-pages 200 --depth 2 --concurrent-sites 5
    python -m scripts.muni_rm_scan --out C:\\path\\to\\output.csv
"""

import argparse
import asyncio
import csv
import socket
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.crawler import Crawler
from app.core.extractor import extract_emails
from app.core.hw_profile import get_hw_profile, HWProfile
from app.core.seed_discoverer import discover_seeds
from app.core.verifier import verify


# (comuna, domain) for all 52 RM comunas + ACHM.
# Domains are reused from the vetted list already in
# app/core/seed_discoverer.py (_CL_MUNICIPALITIES). Padre Hurtado is
# not in that list, so its domain is resolved live via DNS instead
# of guessed. achm.cl was given directly by the user, not inferred.
RM_TARGETS: list[tuple[str, str | None]] = [
    ("Cerrillos", "mcerrillos.cl"),
    ("Cerro Navía", "cerronavia.cl"),
    ("Conchalí", "conchali.cl"),
    ("El Bosque", "municipalidadelbosque.cl"),
    ("Estación Central", "municipalidaddeestacioncentral.cl"),
    ("Huechuraba", "huechuraba.cl"),
    ("Independencia", "independencia.cl"),
    ("La Cisterna", "cisterna.cl"),
    ("La Florida", "laflorida.cl"),
    ("La Granja", "municipalidadlagranja.cl"),
    ("La Pintana", "pintana.cl"),
    ("La Reina", "lareina.cl"),
    ("Las Condes", "lascondes.cl"),
    ("Lo Barnechea", "lobarnechea.cl"),
    ("Lo Espejo", "loespejo.cl"),
    ("Lo Prado", "loprado.cl"),
    ("Macul", "munimacul.cl"),
    ("Maipú", "municipalidadmaipu.cl"),
    ("Ñuñoa", "nunoa.cl"),
    ("Pedro Aguirre Cerda", "pedroaguirrecerda.cl"),
    ("Peñalolén", "penalolen.cl"),
    ("Providencia", "providencia.cl"),
    ("Pudahuel", "mpudahuel.cl"),
    ("Quilicura", "muniquilicura.cl"),
    ("Quinta Normal", "quintanormal.cl"),
    ("Recoleta", "recoleta.cl"),
    ("Renca", "renca.cl"),
    ("San Joaquín", "redsanjoaquin.cl"),
    ("San Miguel", "sanmiguel.cl"),
    ("San Ramón", "municipalidadsanramon.cl"),
    ("Santiago", "munistgo.cl"),
    ("Vitacura", "vitacura.cl"),
    ("Puente Alto", "mpuentealto.cl"),
    ("Pirque", "pirque.cl"),
    ("San José de Maipo", "sanjosedemaipo.cl"),
    ("Colina", "colina.cl"),
    ("Lampa", "lampa.cl"),
    ("Tiltil", "tiltil.cl"),
    ("San Bernardo", "sanbernardo.cl"),
    ("Buin", "buin.cl"),
    ("Paine", "paine.cl"),
    ("Calera de Tango", "municaleradetango.cl"),
    ("Melipilla", "melipilla.cl"),
    ("Alhué", "municipalidadalhue.cl"),
    ("Curacaví", "municipalidadcuracavi.cl"),
    ("María Pinto", "mpinto.cl"),
    ("San Pedro", "munisanpedro.cl"),
    ("Talagante", "munitalagante.cl"),
    ("El Monte", "munielmonte.cl"),
    ("Isla de Maipo", "islademaipo.cl"),
    ("Padre Hurtado", None),
    ("Peñaflor", "penaflor.cl"),
    ("ACHM", "achm.cl"),
]

assert len(RM_TARGETS) == 53  # 52 comunas + ACHM

# Candidate domain patterns tried, in order, only for comunas with
# no known domain above. A candidate is only used if it actually
# resolves over DNS — never asserted from guesswork alone.
_CANDIDATE_PATTERNS = [
    "municipalidad{slug}.cl",
    "muni{slug}.cl",
    "{slug}.cl",
    "im{slug}.cl",
    "m{slug}.cl",
]

_ACCENTS = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}


def _slug(name: str) -> str:
    """ASCII, no-spaces slug for building candidate domains."""
    s = name.lower()
    for accented, plain in _ACCENTS.items():
        s = s.replace(accented, plain)
    return ''.join(c for c in s if c.isalnum())


async def _resolve_unknown_domain(name: str) -> str | None:
    """Probe candidate domains for a comuna with no known domain."""
    slug = _slug(name)
    for pattern in _CANDIDATE_PATTERNS:
        candidate = pattern.format(slug=slug)
        try:
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, socket.gethostbyname, candidate
                ),
                timeout=5.0,
            )
            return candidate
        except Exception:
            continue
    return None


def _domain_match(email: str, domain: str) -> bool:
    """True if email's host is exactly domain or a subdomain of it."""
    host = email.rsplit('@', 1)[-1]
    return host == domain or host.endswith('.' + domain)


@dataclass
class MuniResult:
    """One verified email found for one comuna/organisation."""
    comuna: str
    domain: str
    email: str
    source: str
    status: str
    error: str = ""


async def _scan_domain(
    comuna: str,
    domain: str,
    hw: HWProfile,
    max_pages: int,
    max_depth: int,
    verify_mx: bool = True,
) -> list[MuniResult]:
    """Discover seeds, crawl, extract, and verify emails for one domain."""
    print(f"[{comuna}] discovering seeds for {domain}...")
    try:
        seeds = await discover_seeds(domain)
    except Exception as exc:
        print(f"[{comuna}] seed discovery failed: {exc}")
        return []

    if not seeds:
        print(f"[{comuna}] no seeds found, skipping")
        return []

    print(f"[{comuna}] {len(seeds)} seeds, crawling...")

    crawler = Crawler(
        seeds=seeds,
        max_pages=max_pages,
        max_depth=max_depth,
        concurrency=hw.concurrency,
    )

    found: dict[str, str] = {}  # email -> source url
    pages = 0
    async for url, html in crawler.crawl():
        pages += 1
        for record in extract_emails(html, url):
            email = record['email']
            if _domain_match(email, domain) and email not in found:
                found[email] = record['source']
        await asyncio.sleep(hw.request_delay)

    print(f"[{comuna}] crawled {pages} pages, {len(found)} emails found")

    results = []
    for email, source in found.items():
        if not verify_mx:
            results.append(MuniResult(comuna, domain, email, source, "unverified", ""))
            continue
        try:
            vr = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, verify, email, False, None
                ),
                timeout=10.0,
            )
            status = vr.status.name.lower()
            error = vr.error
        except asyncio.TimeoutError:
            status = "unknown"
            error = "verification timed out"
        results.append(MuniResult(comuna, domain, email, source, status, error))

    return results


DOMAIN_TIMEOUT_S = 90.0


async def run(
    max_pages: int,
    max_depth: int,
    concurrent_sites: int,
    out_path: Path,
    only: list[str] | None = None,
    verify_mx: bool = True,
) -> None:
    """Scan RM_TARGETS (or a subset via `only`) concurrently, writing each
    domain's results to CSV as soon as it finishes (not just at the end),
    so progress survives even if a later domain hangs or the run is killed."""
    hw = get_hw_profile()
    print(
        f"Hardware tier: {hw.tier} "
        f"(per-site concurrency={hw.concurrency}, delay={hw.request_delay}s)"
    )

    targets = RM_TARGETS
    if only:
        wanted = {o.lower() for o in only}
        targets = [(c, d) for c, d in RM_TARGETS if c.lower() in wanted]
        missing = wanted - {c.lower() for c, _ in targets}
        if missing:
            print(f"Warning: unknown --only names ignored: {sorted(missing)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(out_path, 'w', newline='', encoding='utf-8')
    writer = csv.writer(csv_file)
    writer.writerow(['comuna', 'domain', 'email', 'source', 'status', 'error'])
    csv_file.flush()
    write_lock = asyncio.Lock()
    total_written = 0

    semaphore = asyncio.Semaphore(concurrent_sites)

    async def bound_scan(comuna: str, domain: str | None) -> None:
        nonlocal total_written
        async with semaphore:
            resolved = domain
            if resolved is None:
                resolved = await _resolve_unknown_domain(comuna)
                if resolved is None:
                    print(f"[{comuna}] could not resolve a domain, skipping")
                    return
                print(f"[{comuna}] resolved domain: {resolved}")
            try:
                results = await asyncio.wait_for(
                    _scan_domain(comuna, resolved, hw, max_pages, max_depth, verify_mx),
                    timeout=DOMAIN_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                print(f"[{comuna}] timed out after {DOMAIN_TIMEOUT_S:.0f}s, skipping")
                return

            async with write_lock:
                for r in results:
                    writer.writerow([r.comuna, r.domain, r.email, r.source, r.status, r.error])
                csv_file.flush()
                total_written += len(results)

    try:
        await asyncio.gather(*[bound_scan(c, d) for c, d in targets])
    finally:
        csv_file.close()

    print(f"\nDone. {total_written} emails across {len(targets)} targets written to {out_path}")


def _default_out_path() -> Path:
    """Default output path on the user's Desktop, dated."""
    return Path.home() / 'Desktop' / f'RadarCL-RM-Municipios-{date.today().isoformat()}.csv'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--max-pages', type=int, default=150,
        help='Max pages crawled per site (default 150)',
    )
    parser.add_argument(
        '--depth', type=int, default=2,
        help='Max link-follow depth per site (default 2)',
    )
    parser.add_argument(
        '--concurrent-sites', type=int, default=5,
        help='How many municipalities to scan in parallel (default 5)',
    )
    parser.add_argument(
        '--out', type=Path, default=None,
        help='Output CSV path (default: Desktop)',
    )
    parser.add_argument(
        '--only', type=str, default=None,
        help='Comma-separated comuna names to scan (default: all 53)',
    )
    parser.add_argument(
        '--no-mx-verify', action='store_true',
        help=(
            'Skip the MX-lookup verification stage and just record '
            'syntax-checked emails as "unverified". Use this when MX/DNS '
            'lookups are unreliable in the current network environment '
            '(verification would otherwise cost ~5-10s per email and can '
            'cause high-yield domains to hit the per-domain timeout).'
        ),
    )
    args = parser.parse_args()

    out_path = args.out or _default_out_path()
    only = [s.strip() for s in args.only.split(',')] if args.only else None
    asyncio.run(run(
        args.max_pages, args.depth, args.concurrent_sites, out_path, only,
        verify_mx=not args.no_mx_verify,
    ))


if __name__ == '__main__':
    main()
