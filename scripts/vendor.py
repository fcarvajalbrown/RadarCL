"""
Rebuild or verify the vendored dependency set in vendor/.

RadarCL commits its core dependencies as wheels so the project stays
installable if a package is removed from PyPI - see ADR-0008. This script
is the only supported way to regenerate that directory, so the contents
stay reproducible rather than being whatever someone had locally.

What it produces
----------------
vendor/*.whl              Wheels for this platform, resolved from
                          requirements-core.txt.
vendor/*.tar.gz           Source fallbacks for the two packages that ship
                          compiled extensions (lxml, psutil), so other
                          platforms and Python versions can still build
                          offline given a C toolchain.
vendor/SHA256SUMS.txt     Integrity manifest for everything above.
requirements-core.lock    Exact pinned versions with --hash entries,
                          usable with pip install --require-hashes.

Usage
-----
    python scripts/vendor.py            Rebuild vendor/ and the lock file.
    python scripts/vendor.py --check    Verify vendor/ against SHA256SUMS.

Installing offline from the result:
    pip install --no-index --find-links=vendor -r requirements-core.txt
"""

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

# Packages with compiled extensions, for which a portable source
# distribution is vendored alongside the platform-specific wheel.
_SDIST_FALLBACKS: list[str] = ['lxml', 'psutil']

_ROOT = Path(__file__).resolve().parent.parent
_VENDOR = _ROOT / 'vendor'
_REQUIREMENTS = _ROOT / 'requirements-core.txt'
_CHECKSUMS = _VENDOR / 'SHA256SUMS.txt'
_LOCK = _ROOT / 'requirements-core.lock'


def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _artifacts() -> list[Path]:
    """Return every vendored wheel and sdist, sorted by filename."""
    return sorted(
        [p for p in _VENDOR.iterdir()
         if p.suffix == '.whl' or p.name.endswith('.tar.gz')],
        key=lambda p: p.name.lower(),
    )


def _split_name_version(filename: str) -> tuple[str, str]:
    """
    Extract (package_name, version) from a wheel or sdist filename.

    Wheels are {name}-{version}-{python}-{abi}-{platform}.whl and sdists
    are {name}-{version}.tar.gz, so in both cases the version is the
    second hyphen-separated field from the left.
    """
    stem = filename[:-len('.tar.gz')] if filename.endswith('.tar.gz') \
        else filename[:-len('.whl')]
    parts = stem.split('-')
    return parts[0], parts[1]


def download() -> None:
    """Download the core wheels and the sdist fallbacks into vendor/."""
    _VENDOR.mkdir(exist_ok=True)

    print(f"Downloading wheels from {_REQUIREMENTS.name}...")
    subprocess.run(
        [sys.executable, '-m', 'pip', 'download',
         '-r', str(_REQUIREMENTS), '-d', str(_VENDOR), '-q'],
        check=True,
    )

    # `pip download --no-binary :all:` builds each package to resolve its
    # metadata, which needs a C toolchain for lxml. Fetch the sdists
    # straight from the PyPI JSON API instead, which does not.
    import httpx

    print("Fetching source fallbacks...")
    for name in _SDIST_FALLBACKS:
        version = _installed_version(name)
        meta = httpx.get(
            f'https://pypi.org/pypi/{name}/{version}/json', timeout=30
        ).json()
        sdists = [u for u in meta['urls'] if u['packagetype'] == 'sdist']
        if not sdists:
            print(f"  {name} {version}: no sdist published, skipping")
            continue
        url = sdists[0]
        target = _VENDOR / url['filename']
        target.write_bytes(
            httpx.get(url['url'], timeout=120, follow_redirects=True).content
        )
        print(f"  {url['filename']}")


def _installed_version(name: str) -> str:
    """Return the version of `name` already downloaded as a wheel."""
    for path in _VENDOR.glob(f'{name}-*.whl'):
        return _split_name_version(path.name)[1]
    raise SystemExit(
        f"error: no wheel for {name} in vendor/; run without --check first"
    )


def write_checksums() -> None:
    """Write vendor/SHA256SUMS.txt covering every vendored artifact."""
    lines = [f"{_sha256(p)}  {p.name}" for p in _artifacts()]
    _CHECKSUMS.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"Wrote {_CHECKSUMS.relative_to(_ROOT)} ({len(lines)} artifacts)")


def write_lock() -> None:
    """
    Write requirements-core.lock: exact versions with --hash entries.

    Packages that have both a wheel and an sdist vendored get a --hash for
    each, since pip verifies whichever artifact it selects.
    """
    hashes: dict[tuple[str, str], list[str]] = {}
    for path in _artifacts():
        key = _split_name_version(path.name)
        hashes.setdefault(key, []).append(_sha256(path))

    lines = [
        "# Generated by scripts/vendor.py - do not edit by hand.",
        "# Exact versions of the vendored core dependencies (ADR-0008).",
        "#",
        "# Offline install:",
        "#   pip install --no-index --find-links=vendor \\",
        "#       --require-hashes -r requirements-core.lock",
        "",
    ]
    for (name, version), digests in sorted(hashes.items()):
        entry = [f"{name}=={version}"]
        entry += [f"    --hash=sha256:{d}" for d in sorted(digests)]
        lines.append(' \\\n'.join(entry))

    _LOCK.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"Wrote {_LOCK.relative_to(_ROOT)} ({len(hashes)} packages)")


def check() -> int:
    """Verify vendor/ against SHA256SUMS.txt. Returns a process exit code."""
    if not _CHECKSUMS.exists():
        print(f"error: {_CHECKSUMS} not found", file=sys.stderr)
        return 1

    expected = {}
    for line in _CHECKSUMS.read_text(encoding='utf-8').splitlines():
        if line.strip():
            digest, name = line.split('  ', 1)
            expected[name] = digest

    problems = 0
    for path in _artifacts():
        if path.name not in expected:
            print(f"UNTRACKED  {path.name}")
            problems += 1
        elif _sha256(path) != expected[path.name]:
            print(f"MISMATCH   {path.name}")
            problems += 1

    for name in expected:
        if not (_VENDOR / name).exists():
            print(f"MISSING    {name}")
            problems += 1

    if problems:
        print(f"\n{problems} problem(s) found.", file=sys.stderr)
        return 1

    print(f"OK: {len(expected)} artifacts match SHA256SUMS.txt")
    return 0


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Rebuild or verify RadarCL's vendored dependencies.",
    )
    parser.add_argument(
        '--check', action='store_true',
        help='Verify vendor/ against SHA256SUMS.txt instead of rebuilding.',
    )
    args = parser.parse_args()

    if args.check:
        return check()

    download()
    write_checksums()
    write_lock()
    return 0


if __name__ == '__main__':
    sys.exit(main())
