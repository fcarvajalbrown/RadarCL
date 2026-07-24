"""
Extract a version's section from CHANGELOG.md as GitHub release-body text.

Why this script exists rather than a copy-paste step:

GitHub renders a **release body** with hard line breaks enabled, so every
newline becomes a `<br>`. A Markdown **file** viewed in the repository does
not behave that way; it reflows paragraphs normally. CHANGELOG.md is hard
wrapped at 72 columns, which is right for the file and wrong for the
release page, where it comes out as a ragged left-aligned column that uses
about half the available width.

So the published copy is unwrapped: paragraphs and list items are joined
onto one line each, and the renderer decides where lines break. Blank
lines, headings and list-item boundaries survive. Relative `docs/` links
are rewritten to absolute URLs pinned at the tag, since a relative link in
a release body does not resolve.

Usage:
    python scripts/release_notes.py 0.3.5 > notes.md
    gh release create v0.3.5 installer\\RadarCL-v0.3.5-Setup.exe \\
        --title "RadarCL v0.3.5" --notes-file notes.md
"""

import argparse
import re
import sys
from pathlib import Path

REPO = 'https://github.com/fcarvajalbrown/RadarCL'
CHANGELOG = Path(__file__).resolve().parent.parent / 'CHANGELOG.md'


def extract(text: str, version: str) -> str:
    """
    Return the body of one version's section, heading excluded.

    The heading is dropped because the release already carries the version
    in its title, and repeating it wastes the first line of the page.
    """
    pattern = re.compile(
        rf'^## \[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^## |\Z)',
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        raise SystemExit(
            f"No hay una seccion para la version {version} en CHANGELOG.md."
        )
    return match.group(1)


def unwrap(section: str) -> str:
    """Join each paragraph and each list item onto a single line."""
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            out.append(' '.join(buf))
            buf.clear()

    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            out.append('')
        elif stripped.startswith('#'):
            flush()
            out.append(stripped)
        elif stripped.startswith(('- ', '* ')):
            flush()
            buf.append(stripped)
        else:
            buf.append(stripped)
    flush()

    body = '\n'.join(out).strip() + '\n'
    return re.sub(r'\n{3,}', '\n\n', body)


def absolutize(body: str, tag: str) -> str:
    """Pin repo-relative doc links to the tag so they resolve off-site."""
    return body.replace('(docs/', f'({REPO}/blob/{tag}/docs/')


def main(argv: list[str] | None = None) -> int:
    """Print the release body for the requested version to stdout."""
    parser = argparse.ArgumentParser(
        description=(
            'Extrae una version del CHANGELOG como cuerpo de release, '
            'desenvuelto para que GitHub lo reflowee.'
        )
    )
    parser.add_argument('version', help='Por ejemplo 0.3.5')
    parser.add_argument(
        '--tag', default=None,
        help='Etiqueta para los enlaces (por defecto v<version>).',
    )
    args = parser.parse_args(argv)

    tag = args.tag or f'v{args.version}'
    text = CHANGELOG.read_text(encoding='utf-8')
    sys.stdout.write(absolutize(unwrap(extract(text, args.version)), tag))
    return 0


if __name__ == '__main__':
    sys.exit(main())
