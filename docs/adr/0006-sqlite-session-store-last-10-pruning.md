# 0006 - SQLite session store with last-10 pruning

## Status
Accepted

## Date
2026-07-23 (retroactive - decision predates this record)

## Deciders
Felipe Carvajal Brown

## Context
RadarCL sessions collect potentially sensitive scraped contact data (emails,
source URLs). The app needed some persistence to support resuming/reviewing
past runs, but the same data is also explicitly meant not to accumulate
indefinitely on a user's machine or get committed to version control (see
`.gitignore`'s `*.db`/`~/.radarcl/` and `RadarCL-*.csv` exclusions).

## Decision
`app/core/session.py` stores sessions and their discovered emails in a local
SQLite database at `~/.radarcl/sessions.db` (stdlib `sqlite3`, no external
dependency). Every call to `new_session()` prunes the table down to the most
recent 10 sessions (`_prune_old_sessions`), so history never grows unbounded.

## Consequences
- Zero extra runtime dependency for persistence (SQLite ships with Python).
- Users always have their last 10 sessions' data available locally, but
  older scraped data is deleted automatically rather than piling up.
- There's no export/backup step before pruning - if a user wants to keep
  session #11's data, they need to have already exported it (see
  `app/core/exporter.py`'s auto-export-to-Desktop-CSV behaviour) before
  starting 10 more sessions.

## Alternatives considered
- **No persistence at all, in-memory only**: simplest, but loses all
  discovered emails if the app crashes or closes mid-verification, with no
  way to resume.
- **Unlimited history**: keeps every session ever run, but conflicts with the
  project's own stance (per `.gitignore` and the exporter's Desktop-only
  export) of not accumulating scraped personal data indefinitely.
- **A heavier embedded DB (e.g. a document store)**: unnecessary for a simple
  two-table relational schema (`sessions`, `emails`) that SQLite handles
  natively.
