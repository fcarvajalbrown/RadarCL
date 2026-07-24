# 0002 - Async core with a QThread worker bridge

## Status
Accepted

## Date
2026-07-23 (retroactive - decision predates this record)

## Deciders
Felipe Carvajal Brown

## Context
Crawling, seed discovery, and verification are I/O-bound (HTTP, DNS, SMTP)
and benefit from `asyncio` concurrency. Qt's event loop and `asyncio`'s event
loop don't share a thread naturally, and `app/core/` logic (see
[ADR-0001](0001-pyside6-gui-stack.md)) needed to stay independently testable
without pulling in Qt.

## Decision
`app/core/` contains only plain async functions and dataclasses - no Qt
imports anywhere. `app/workers/` contains `QThread` subclasses
(`CrawlerWorker`, `VerifierWorker`) that are the *only* place Qt and `core`
meet: each worker's `run()` calls `asyncio.run(...)` on a `core` coroutine
inside the background thread, and re-emits results as Qt signals
(`email_found`, `progress`, `verify_finished`, etc.) for the GUI thread.
`app/ui/` never calls `core` directly - only worker signals.

## Consequences
- `core` functions/tests run with plain `pytest` and `asyncio`, no Qt
  application or event loop needed (see `tests/test_extractor.py`,
  `tests/test_verifier.py`).
- Every new async capability needs its own thin `QThread` wrapper to reach
  the GUI - see `app/workers/crawler_worker.py` and
  `app/workers/verifier_worker.py` as the reference pattern.
- Pause/resume and cancellation are threaded through explicitly
  (`asyncio.Event` for pause, a `_stop_flag` checked in the loop for stop) -
  see `Crawler.pause`/`resume` in `app/core/crawler.py` - since a plain
  `QThread.terminate()` can't cleanly interrupt an `asyncio` loop.

## Alternatives considered
- **`QThreadPool` + `QRunnable` with sync HTTP calls**: simpler Qt-native
  concurrency model, but would mean rewriting the crawler/verifier on top of
  blocking `requests`/`smtplib` calls per task rather than `asyncio`+`httpx`,
  losing the ability to run many concurrent fetches per worker.
- **Qt's own async integration (`qasync`)**: would let `core` run on Qt's own
  event loop directly, removing the worker-thread indirection, but adds a
  third-party dependency and blurs the "core has zero Qt" boundary that
  keeps `core` testable in isolation.
