# 0001 - PySide6 (Qt6) as the GUI stack

## Status
Accepted

## Date
2026-07-23 (retroactive - decision predates this record)

## Deciders
Felipe Carvajal Brown

## Context
RadarCL needed a Windows desktop GUI: a control panel for session setup, a live
terminal-style feed of discovered emails, and a results table shown after
verification. The app also needed to run long crawl/verify jobs without
freezing the UI, and ship as a standalone Windows `.exe` for non-technical
users (municipal staff, colleagues) who won't run it from source.

## Decision
Use PySide6 (Qt6) for the GUI, with all Qt-specific code confined to
`app/ui/` and `app/workers/`. Long-running work (crawling, verification, seed
discovery) runs on `QThread` subclasses that emit Qt signals back to the GUI
thread; `app/core/` itself has zero Qt imports.

## Consequences
- A native, responsive desktop app that doesn't block on network I/O.
- PyInstaller can package PySide6 apps into a single `.exe` reasonably well
  (see `dist/RadarCL.exe`, `RadarCL.iss`), which a browser-based tool would
  not need but a plain Tkinter app might have made packaging simpler for.
- Every new feature that touches both business logic and the UI must respect
  the `core` (no Qt) / `workers` (QThread bridge) / `ui` (Qt only) boundary -
  see [ADR-0002](0002-async-core-qthread-worker-bridge.md).
- Qt/PySide6 is a heavier dependency and larger install/exe size than a
  minimal toolkit, traded for a native look, signals/slots concurrency model,
  and mature Windows packaging support.

## Alternatives considered
- **Web-based (Flask/FastAPI + browser UI)**: would decouple the frontend
  from Python packaging entirely, but adds a server process and browser
  dependency for a tool meant to be a simple double-click `.exe` for
  non-technical municipal/civic-tech users.
- **Tkinter**: ships with Python, smaller footprint, but weaker widget set
  and harder to build the terminal-feed/results-table/splitter layout RadarCL
  needed without significant custom widget work.
