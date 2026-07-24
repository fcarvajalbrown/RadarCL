# 0003 - Two-phase crawl scope (.cl-only, then optional expansion)

## Status
Accepted

## Date
2026-07-23 (retroactive - decision predates this record)

## Deciders
Felipe Carvajal Brown

## Context
RadarCL's purpose is finding `.cl` email addresses. Restricting crawling to
`.cl` domains keeps the crawl fast and on-target, but some `.cl`
organisations publish staff contact info on non-`.cl` pages they link to
(PDF hosts, social profiles, partner sites), so a purely `.cl`-only crawl
can miss real emails that are still `.cl` addresses.

## Decision
`Crawler` (`app/core/crawler.py`) runs in two phases. Phase 1 only follows
links to `.cl` domains (`is_cl_domain`). If `phase2_enabled` is set and
`phase1_timeout` elapses, Phase 2 activates and the crawler starts following
non-`.cl` links too - but the *email filter* (`extractor.extract_emails`
combined with the target-domain check in `CrawlerWorker._crawl`) always stays
`.cl`-only, regardless of phase. Phase 2 is opt-in per session via a checkbox
in the control panel.

## Consequences
- Default behaviour (Phase 2 off) is fast and tightly scoped - safe for a
  quick run.
- Users who need broader reach can opt into Phase 2 without ever risking
  non-`.cl` emails leaking into results, since the email filter is
  independent of which pages get crawled.
- The timeout-based phase switch is a coarse trigger (wall-clock elapsed,
  not "Phase 1 exhausted") - a session with few `.cl` pages left will still
  wait out the full `phase1_timeout` before expanding.

## Alternatives considered
- **Single-phase, always `.cl`-only**: simpler, but would miss emails
  published on non-`.cl` pages linked from `.cl` sites (e.g. a PDF staff
  directory hosted off-domain).
- **Single-phase, always follow all links**: maximal reach, but crawls far
  more pages than necessary for a tool whose entire purpose is `.cl` contacts,
  and risks wandering into unrelated large sites.
- **Depth-based phase switch instead of timeout**: e.g. expand to non-`.cl`
  only after `.cl` link depth is exhausted; more precise, but harder to
  reason about for users tuning session length in the control panel's
  "Search .cl sites for" dropdown.
