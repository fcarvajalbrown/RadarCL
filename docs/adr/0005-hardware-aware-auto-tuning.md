# 0005 - Hardware-aware auto-tuning of crawl settings

## Status
Accepted

## Date
2026-07-23 (retroactive - decision predates this record)

## Deciders
Felipe Carvajal Brown

## Context
RadarCL is meant to run on whatever machine a municipal or civic-tech user
has on hand, not just modern developer laptops - including old office
desktops (the codebase's own comment cites "Dell Optiplex etc." as a target).
A fixed concurrency/delay/max-pages setting tuned for a fast machine can
overload a low-spec one; a fixed conservative setting wastes capacity on a
fast one.

## Decision
`get_hw_profile()` (`app/core/hw_profile.py`) detects total RAM and physical
CPU core count at startup via `psutil` and buckets the machine into `low`
(RAM<4GB or cores<=2), `medium`, or `high` tiers, each with its own
concurrency, request delay, and max-pages defaults. The control panel surfaces
the detected tier as a badge and feeds these values into `CrawlerWorker` as
its defaults; the user isn't asked to tune raw concurrency numbers directly.

## Consequences
- Out-of-the-box behaviour is safe on old hardware without the user needing
  to know what "concurrency" means.
- Detection is a one-shot decision made at startup - it doesn't adapt if
  system load changes mid-session (e.g. another heavy app launches).
- The three tiers are coarse cutoffs; a machine just below a threshold gets
  meaningfully more conservative settings than one just above it, with no
  smooth interpolation.

## Alternatives considered
- **Fixed, user-tunable settings only**: puts the burden of choosing safe
  values on users who are explicitly not expected to be technical (municipal
  staff), risking either a frozen low-spec machine or needlessly slow crawls
  on a capable one.
- **Runtime-adaptive tuning (monitor CPU/RAM load during the crawl and adjust
  concurrency live)**: more responsive, but meaningfully more complex to
  implement and reason about than a one-shot profile check at startup, for a
  tool whose sessions are run interactively and can be paused manually anyway.
