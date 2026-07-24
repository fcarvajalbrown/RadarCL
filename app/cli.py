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
from app.core.exporter import export_valid
from app.core.pipeline import verify_all
from app.core.seed_discoverer import discover_seeds
from app.core.session import new_session, save_email


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
        help='Ruta del CSV de salida. Sin esto no se escribe ningun archivo.',
    )
    verify_cmd.add_argument(
        '--no-session', action='store_true',
        help='No registra la ejecucion en ~/.radarcl/sessions.db.',
    )
    verify_cmd.add_argument(
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


def write_results(results: list[dict], output: str | None, quiet: bool) -> None:
    """
    Write the CSV export and the stderr summary for a finished run.

    The Desktop auto-export the GUI performs is deliberately never
    triggered here: exporter.default_export_path() creates ~/Desktop, which
    is wrong on a headless machine. The CLI exports only on an explicit
    --output.
    """
    counts = {'valid': 0, 'invalid': 0, 'unknown': 0}
    for record in results:
        counts[record['status']] = counts.get(record['status'], 0) + 1

    if output is not None:
        path = export_valid(results, Path(output))
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


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a list of addresses read from a file or stdin."""
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
        write_results(results, args.output, args.quiet)
        return 130

    _persist(session_id, results)
    write_results(results, args.output, args.quiet)
    return 0


_COMMANDS = {
    'discover': cmd_discover,
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
