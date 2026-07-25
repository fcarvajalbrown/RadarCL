"""
Headless command-line entry point.

Drives app/core/ directly with no Qt dependency, so RadarCL can be
scripted, run from cron, and used on machines without the GUI stack.

Convention: stdout carries data only (one seed URL per line, or
tab-separated email/status/source rows) so output pipes cleanly. Every
human-readable message goes to stderr, in Spanish, and is silenced by
--quiet.

Run with: python -m app.cli --help
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app import __version__
from app.core.exporter import export, infer_format
from app.core.hw_profile import get_hw_profile
from app.core.pipeline import Discovery, crawl_and_extract, verify_all
from app.core.seed_discoverer import discover_seeds
from app.core.session import new_session, save_email, update_session_totals


def log(message: str, quiet: bool) -> None:
    """Write a progress message to stderr unless quiet is set."""
    if not quiet:
        print(message, file=sys.stderr)


def format_row(email: str, status: str, source: str) -> str:
    """Format one result as a tab-separated stdout row."""
    return f"{email}\t{status}\t{source}"


def read_seeds(path: str) -> list[str]:
    """
    Read seed URLs from a file, one per line.

    Blank lines and lines starting with '#' are ignored.
    """
    seeds: list[str] = []
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith('#'):
                seeds.append(line)
    return seeds


def read_email_list(path: str) -> list[tuple[str, str]]:
    """
    Read (email, source_url) pairs from a file, or from stdin if path is '-'.

    Accepts either one bare address per line, or the tab-separated
    email/status/source rows that `scan` writes, so a scan's output can be
    fed straight back in. Blank lines and '#' comments are ignored. Source
    is empty for bare addresses.
    """
    stream = sys.stdin if path == '-' else open(path, encoding='utf-8')
    try:
        pairs: list[tuple[str, str]] = []
        for line in stream:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            fields = line.split('\t')
            email = fields[0].strip()
            source = fields[2].strip() if len(fields) >= 3 else ''
            if email:
                pairs.append((email, source))
        return pairs
    finally:
        if stream is not sys.stdin:
            stream.close()


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for all subcommands."""
    parser = argparse.ArgumentParser(
        prog='radarcl',
        description=(
            'RadarCL: descubrimiento y verificacion de correos .cl '
            'desde la linea de comandos.'
        ),
    )
    parser.add_argument(
        '--version', action='version', version=f'RadarCL {__version__}'
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    discover = subparsers.add_parser(
        'discover',
        help='Descubre URLs semilla para un dominio, sin rastrear.',
    )
    discover.add_argument(
        'domain', help='Dominio objetivo, por ejemplo nunoa.cl'
    )
    discover.add_argument(
        '--max-seeds', type=int, default=20,
        help='Numero maximo de semillas a devolver (por defecto 20).',
    )
    discover.add_argument(
        '--no-duckduckgo', action='store_true',
        help='Omite la etapa de busqueda en DuckDuckGo.',
    )
    discover.add_argument(
        '--quiet', action='store_true',
        help='Silencia los mensajes de progreso en stderr.',
    )

    verify_cmd = subparsers.add_parser(
        'verify',
        help='Verifica una lista de direcciones desde un archivo o stdin.',
    )
    verify_cmd.add_argument(
        '--input', required=True,
        help="Archivo con una direccion por linea, o '-' para stdin.",
    )
    verify_cmd.add_argument(
        '--no-smtp', action='store_true',
        help='Omite la etapa SMTP (equivale al modo rapido de la interfaz).',
    )
    verify_cmd.add_argument(
        '--output', default=None,
        help=(
            'Ruta del archivo de salida. Sin esto no se escribe ningun '
            'archivo.'
        ),
    )
    verify_cmd.add_argument(
        '--format', choices=['csv', 'json', 'html'], default=None,
        help=(
            'Formato de salida. Por defecto se deduce de la extension de '
            '--output. El CSV lleva solo las direcciones validas; JSON y '
            'HTML llevan todos los estados.'
        ),
    )
    verify_cmd.add_argument(
        '--no-session', action='store_true',
        help='No registra la ejecucion en ~/.radarcl/sessions.db.',
    )
    verify_cmd.add_argument(
        '--quiet', action='store_true',
        help='Silencia los mensajes de progreso en stderr.',
    )

    scan = subparsers.add_parser(
        'scan',
        help='Pipeline completo: descubre, rastrea, extrae y verifica.',
    )
    scan.add_argument(
        'domain',
        help='Dominio de correo objetivo, por ejemplo nunoa.cl',
    )
    scan.add_argument(
        '--seeds', default=None,
        help=(
            'Archivo con URLs semilla, una por linea. Omite el '
            'descubrimiento automatico.'
        ),
    )
    scan.add_argument(
        '--pattern', default='',
        help=(
            'Plantilla para generar candidatos, por ejemplo '
            '{first}.{last}. Sin esto no se generan candidatos.'
        ),
    )
    scan.add_argument(
        '--max-seeds', type=int, default=20,
        help='Numero maximo de semillas a descubrir (por defecto 20).',
    )
    scan.add_argument(
        '--no-duckduckgo', action='store_true',
        help='Omite la etapa de busqueda en DuckDuckGo.',
    )
    scan.add_argument(
        '--max-pages', type=int, default=None,
        help='Limite de paginas. Por defecto lo fija el perfil de hardware.',
    )
    scan.add_argument(
        '--concurrency', type=int, default=None,
        help='Peticiones simultaneas. Por defecto lo fija el hardware.',
    )
    scan.add_argument(
        '--delay', type=float, default=None,
        help='Segundos entre peticiones. Por defecto lo fija el hardware.',
    )
    scan.add_argument(
        '--phase2', action='store_true',
        help=(
            'Permite seguir enlaces fuera de .cl. El filtro de correos '
            'sigue siendo solo .cl.'
        ),
    )
    scan.add_argument(
        '--phase1-timeout', type=float, default=None,
        help='Segundos antes de activar la fase 2.',
    )
    scan.add_argument(
        '--no-smtp', action='store_true',
        help='Omite la etapa SMTP (equivale al modo rapido de la interfaz).',
    )
    scan.add_argument(
        '--output', default=None,
        help=(
            'Ruta del archivo de salida. Sin esto no se escribe ningun '
            'archivo.'
        ),
    )
    scan.add_argument(
        '--format', choices=['csv', 'json', 'html'], default=None,
        help=(
            'Formato de salida. Por defecto se deduce de la extension de '
            '--output. El CSV lleva solo las direcciones validas; JSON y '
            'HTML llevan todos los estados.'
        ),
    )
    scan.add_argument(
        '--no-session', action='store_true',
        help='No registra la ejecucion en ~/.radarcl/sessions.db.',
    )
    scan.add_argument(
        '--quiet', action='store_true',
        help='Silencia los mensajes de progreso en stderr.',
    )

    return parser


def cmd_discover(args: argparse.Namespace) -> int:
    """Run seed discovery and print the seeds to stdout."""
    domain = args.domain.lstrip('@').lower().strip()
    log(f"Buscando semillas para {domain}...", args.quiet)

    seeds = asyncio.run(discover_seeds(
        domain,
        use_duckduckgo=not args.no_duckduckgo,
        max_seeds=args.max_seeds,
    ))

    for seed in seeds:
        print(seed)

    log(f"{len(seeds)} semillas encontradas.", args.quiet)
    return 0


def resolve_format(output: str | None, fmt: str | None) -> str | None:
    """
    Settle the export format before any slow work starts.

    Returns None when there is nothing to export. Raises ValueError when
    the extension is unrecognised and no --format was given, so a `scan`
    with a typo in --output fails in the first second instead of after a
    ten-minute crawl.
    """
    if output is None:
        return None
    return fmt or infer_format(output)


def write_results(
    results: list[dict],
    output: str | None,
    quiet: bool,
    fmt: str | None = None,
) -> None:
    """
    Write the export and the stderr summary for a finished run.

    The Desktop auto-export the GUI performs is deliberately never
    triggered here: exporter.default_export_path() creates ~/Desktop, which
    is wrong on a headless machine. The CLI exports only on an explicit
    --output.
    """
    counts = {'valid': 0, 'invalid': 0, 'unknown': 0}
    for record in results:
        counts[record['status']] = counts.get(record['status'], 0) + 1

    if output is not None:
        path = export(results, Path(output), fmt)
        log(f"Exportado a {path}", quiet)

    log(
        f"Resumen: {counts['valid']} validos, "
        f"{counts['unknown']} desconocidos, "
        f"{counts['invalid']} invalidos.",
        quiet,
    )


def _persist(session_id: int | None, results: list[dict]) -> None:
    """
    Save results to the session store, if a session was opened.

    One connection per row, matching the existing session module's
    behaviour; acceptable at RadarCL's scale of dozens to hundreds.
    """
    if session_id is None:
        return
    for record in results:
        save_email(
            session_id, record['email'], record['source'], record['status']
        )
    update_session_totals(
        session_id,
        len(results),
        sum(1 for r in results if r['status'] == 'valid'),
    )


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a list of addresses read from a file or stdin."""
    try:
        export_format = resolve_format(args.output, args.format)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    pairs = read_email_list(args.input)
    if not pairs:
        print("No se leyo ninguna direccion.", file=sys.stderr)
        return 1

    log(f"Verificando {len(pairs)} direcciones...", args.quiet)

    session_id = None
    if not args.no_session:
        session_id = new_session('(verify)', [])

    results: list[dict] = []
    try:
        for record in verify_all(pairs, smtp_enabled=not args.no_smtp):
            results.append(record)
            print(format_row(
                record['email'], record['status'], record['source']
            ))
    except KeyboardInterrupt:
        log("Interrumpido. Se conservan los resultados parciales.", args.quiet)
        _persist(session_id, results)
        write_results(results, args.output, args.quiet, export_format)
        return 130

    _persist(session_id, results)
    write_results(results, args.output, args.quiet, export_format)
    return 0


async def _crawl_into(
    sink: list[Discovery],
    seeds: list[str],
    domain: str,
    args: argparse.Namespace,
    profile,
) -> None:
    """
    Run the crawl, appending each discovery to sink.

    Results accumulate in a caller-owned list rather than being returned,
    so a Ctrl+C part-way through still leaves the caller holding everything
    found up to that point.
    """
    async for discovery in crawl_and_extract(
        seeds,
        target_domain=domain,
        phase2_enabled=args.phase2,
        phase1_timeout=args.phase1_timeout,
        max_pages=args.max_pages or profile.max_pages,
        pattern=args.pattern,
        request_delay=(
            args.delay if args.delay is not None else profile.request_delay
        ),
        concurrency=args.concurrency or profile.concurrency,
        on_page=lambda url, count: log(f"[crawl] {url}", args.quiet),
    ):
        sink.append(discovery)


def cmd_scan(args: argparse.Namespace) -> int:
    """Run the full pipeline: discover, crawl, extract, verify."""
    try:
        export_format = resolve_format(args.output, args.format)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    domain = args.domain.lstrip('@').lower().strip()
    profile = get_hw_profile()
    log(
        f"Perfil de hardware: {profile.tier} "
        f"({profile.ram_gb} GB RAM, {profile.cpu_cores} nucleos)",
        args.quiet,
    )

    if args.seeds:
        seeds = read_seeds(args.seeds)
        log(f"{len(seeds)} semillas leidas de {args.seeds}.", args.quiet)
    else:
        log(f"Buscando semillas para {domain}...", args.quiet)
        seeds = asyncio.run(discover_seeds(
            domain,
            use_duckduckgo=not args.no_duckduckgo,
            max_seeds=args.max_seeds,
        ))
        log(f"{len(seeds)} semillas encontradas.", args.quiet)

    if not seeds:
        print(
            "No se encontraron semillas. Use --seeds para indicarlas "
            "manualmente.",
            file=sys.stderr,
        )
        return 1

    session_id = None
    if not args.no_session:
        session_id = new_session(domain, seeds)

    discoveries: list[Discovery] = []
    interrupted = False
    try:
        asyncio.run(_crawl_into(discoveries, seeds, domain, args, profile))
    except KeyboardInterrupt:
        interrupted = True
        log(
            "Rastreo interrumpido. Se verifica lo encontrado hasta ahora.",
            args.quiet,
        )

    log(f"{len(discoveries)} correos encontrados.", args.quiet)

    pairs = [(d.email, d.source_url, d.evidence, d.generated)
             for d in discoveries]
    results: list[dict] = []
    try:
        for record in verify_all(pairs, smtp_enabled=not args.no_smtp):
            results.append(record)
            print(format_row(
                record['email'], record['status'], record['source']
            ))
    except KeyboardInterrupt:
        interrupted = True
        log(
            "Verificacion interrumpida. Se conservan los resultados "
            "parciales.",
            args.quiet,
        )

    _persist(session_id, results)
    write_results(results, args.output, args.quiet, export_format)
    return 130 if interrupted else 0


_COMMANDS = {
    'discover': cmd_discover,
    'scan': cmd_scan,
    'verify': cmd_verify,
}


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the requested subcommand."""
    args = build_parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except KeyboardInterrupt:
        log("Interrumpido por el usuario.", getattr(args, 'quiet', False))
        return 130
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
