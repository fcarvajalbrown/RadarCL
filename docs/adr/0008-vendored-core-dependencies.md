# 0008 - Vendored core dependencies, hash-pinned GUI dependencies

## Status
Accepted

## Date
2026-07-24

## Deciders
Felipe Carvajal Brown

## Context
RadarCL declares its dependencies as version ranges in `requirements.txt`
and `requirements-core.txt` and resolves them from PyPI at install time. If
a package were removed from PyPI, the project would stop being installable,
including from a clean checkout of a tagged release.

That risk is real rather than theoretical. PyPI still permits outright
deletion of a project, release, or file. PEP 763 proposed limiting deletion
to a 72-hour window after upload, but it was withdrawn on 21 September 2025
on the grounds that a PEP is not the appropriate venue for PyPI usage
policy, so no such limit is in force. PyPI's own documentation presents
yanking only as "a non-destructive alternative to deletion", which leaves
deletion available. The `atomicwrites` removal in July 2022 required manual
administrator intervention to restore.

Two measurements constrain what can be done about it:

- The core dependency set - what `app/core/` and `app/cli.py` need - is 15
  wheels totalling 5.2 MB. That is small enough to commit.
- The GUI set is 240 MB, and `pyside6_addons-6.11.1-cp310-abi3-win_amd64.whl`
  is 168.8 MB on its own. GitHub hard-blocks any single file over 100 MiB
  from normal git history and warns above 50 MiB. Committing it is not
  possible without Git LFS, whose free tier provides 1 GB of storage and
  1 GB of bandwidth per month - roughly four clones of a 240 MB payload.

A third constraint applies to which artifacts are portable. Thirteen of the
fifteen core wheels are `py3-none-any` and work anywhere. The other two are
not: `lxml` resolves to `cp314-cp314-win_amd64`, locked to both Python 3.14
and Windows x64, and `psutil` to `cp37-abi3-win_amd64`. Since
`pyproject.toml` declares `requires-python = ">=3.12"` and
[ADR-0002](0002-async-core-qthread-worker-bridge.md)'s Qt-free core exists
precisely so the CLI can run on non-Windows machines, vendoring only this
machine's wheels would quietly narrow the supported surface.

## Decision
Vendor the core dependency set into `vendor/`, committed to git, and
hash-pin the GUI set without vendoring it.

- `vendor/` holds the 15 core wheels for Windows x64, plus source
  distributions for `lxml` and `psutil` so other platforms and Python
  versions can build offline given a C toolchain. 9.7 MB total.
- `vendor/SHA256SUMS.txt` is an integrity manifest for every artifact.
- `requirements-core.lock` pins exact versions with `--hash` entries.
  Packages with both a wheel and an sdist carry a hash for each, since pip
  verifies whichever artifact it selects. Offline install:
  `pip install --no-index --find-links=vendor --require-hashes -r requirements-core.lock`
- `requirements-gui.lock` pins PySide6 and PyInstaller by exact version and
  hash. These are not vendored, for the file-size reason above.
- `scripts/vendor.py` is the only supported way to regenerate the directory,
  so its contents stay reproducible. `--check` verifies `vendor/` against
  the manifest.

`requirements.txt` and `requirements-core.txt` keep their `>=` ranges and
remain the ordinary install path. Vendoring is a fallback, not the default.

## Consequences
- A clean checkout stays installable and runnable with no network and no
  PyPI, verified: a fresh virtualenv installed from `vendor/` with
  `--no-index --require-hashes` runs `python -m app.cli` and imports the
  full core pipeline.
- The GUI remains exposed to PyPI availability. This is the accepted
  trade-off: losing PySide6 costs the desktop front end while the crawler,
  verifier, exporter and CLI keep working, and PySide6 is maintained by the
  Qt Company rather than an individual volunteer.
- The repository grows by 9.7 MB, permanently, since git history cannot be
  pruned without a rewrite. Clones get correspondingly larger.
- Dependency upgrades now have a second step: bump the range in
  `requirements-core.txt`, then rerun `scripts/vendor.py` and commit the
  result. A stale `vendor/` that disagrees with `requirements-core.txt` is a
  new failure mode, which `--check` only partially covers - it verifies
  integrity, not currency.
- Vendored binaries are a supply-chain surface in their own right. The
  SHA-256 manifest makes tampering detectable but does not make the original
  artifacts trustworthy; they are exactly what PyPI served on the date they
  were fetched.
- The vendored wheels are Windows x64 and Python 3.14. Other targets fall
  back to the sdists, which require a compiler for `lxml` - a normal
  expectation when building lxml from source, but still a sharper edge than
  a wheel.

## Alternatives considered
- **Vendor everything via Git LFS**: total offline reproducibility including
  the GUI. Rejected because it forces every contributor to install git-lfs,
  inflates clones to 245 MB, and exhausts the free LFS bandwidth quota after
  about four clones - a high running cost to protect a dependency that is
  among the least likely to disappear.
- **Hash-pinned lockfile only, no committed binaries**: keeps the repository
  small and guarantees byte-exact installs. Rejected as the primary measure
  because it does not address removal at all. If a package leaves PyPI, the
  hashes identify what is missing without providing it. Retained as the
  approach for the GUI set, where committing is impossible anyway.
- **Vendor a full wheel matrix across Windows, Linux and macOS for Python
  3.12 through 3.14**: every supported target would install offline with no
  compiler. Rejected for this milestone as roughly 40 MB and 15 to 20 extra
  files that must be regenerated on every dependency bump. The sdist
  fallback covers the same ground at a fraction of the maintenance cost, and
  the matrix can be revisited in a later ADR if the CLI gains real
  non-Windows usage.
- **Do nothing, rely on PyPI**: the status quo. Rejected because deletion
  remains permitted and the mitigation for the core set costs 9.7 MB.
