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

from app import __version__
from app.core.seed_discoverer import discover_seeds


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


_COMMANDS = {
    'discover': cmd_discover,
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
