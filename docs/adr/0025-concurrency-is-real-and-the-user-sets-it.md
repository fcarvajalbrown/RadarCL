# 0025 - Concurrency is real, and the user sets it

## Status
Accepted.

## Date
2026-08-23

## Deciders
Felipe Carvajal Brown

## Context
[ADR-0005](0005-hardware-aware-auto-tuning.md) tunes three crawl settings to the
machine: concurrency 2/3/6, request delay 1.0/0.5/0.2 s, and a page cap of
1000/2000/5000, by `low`/`medium`/`high` tier. The tier badge is shown in the
control panel, so the number is a promise made to the user.

Two of the three are kept. The concurrency one is not. `Crawler.crawl()` awaits
`_fetch` inline inside a single loop, so the semaphore it builds never has more
than one waiter and every crawl RadarCL has ever run was strictly serial. The
declared 2, 3 and 6 describe nothing.

Three scans on 2026-08-23 measured what that costs, all on the `high` tier
(15.8 GB RAM, 8 cores, 0.2 s delay), all capped at 40 pages and 10 seeds so they
would finish:

| Target | Pages read | Blocked | Addresses kept | Wall clock |
|---|---|---|---|---|
| `bhp.com` | 17 | 4 | 0 | 43 s |
| `gecamin.com` | 40, cap reached | 1 | 4 | 30 s |
| `nunoa.cl` | 40, cap reached | 1 | 22 | 78 s, verification included |

Gecamin's 40 pages fit inside a 30-second total that also covered seed discovery
and four DNS verifications, so a page costs at most about 0.6 s. Carrying that
same fetch cost across the tiers as arithmetic rather than measurement, the
`high` cap of 5000 pages is a fifty-minute crawl, `medium` about thirty-five and
`low` about twenty-five.

So the cap is not a budget being spent. It is a ceiling nobody reaches, and what
actually ends a scan is the person watching it give up. Link depth does not bind
either: both crawls that reached the 40-page cap still had a growing frontier,
which is what ten seeds at depth 3 produces on any site of normal size.

Every other number in the profile is arithmetic downstream of the one that does
not work.

## Decision
**Concurrency becomes real.** `Crawler.crawl()` dispatches fetches concurrently
up to the configured limit instead of awaiting each one inline. The tier
defaults of 2/3/6 stay exactly as [ADR-0005](0005-hardware-aware-auto-tuning.md)
set them; this decision does not change what the numbers are, it makes them
describe the crawl.

**The page caps stay as they are, for now.** They are unreachable today because
the crawl is serial. Changing them in the same breath as the fix would be
setting a bound against throughput nobody has measured yet, which is the
invention [ADR-0022](0022-a-parser-is-not-a-source-and-does-not-need-a-gate.md)
refused. The caps are re-derived against a measured parallel crawl, in their own
decision, or left alone.

**The GUI gets a concurrency control, defaulting to the tier value.** The CLI
already takes `--concurrency`; the control panel passes `self._hw.concurrency`
straight through with nothing the user can touch, so the GUI is the only gap.
The tier stays the default, so a user who changes nothing gets what
[ADR-0005](0005-hardware-aware-auto-tuning.md) picked for their machine, and one
who is scanning a small site or a fragile one can move it.

The delay and the page cap stay tier-decided and are not exposed. One control is
being added because one number is being fixed.

## Consequences
- A crawl runs 2 to 6 times faster depending on tier, and the page cap starts
  being approachable rather than theoretical. Whether it is then the right cap
  is the open question above.
- **More load lands on a target site at once**, which is the cost being paid.
  The request delay is unchanged and still applies, so the crawl is faster but
  not unpaced.
- **Pause, resume and stop need rechecking, not assuming.** Today one coroutine
  checks `_pause_event` between pages, and `should_stop` is polled per page in
  `pipeline`. With several fetches in flight, a Stop lands while requests are
  outstanding and a Pause no longer means what it meant. The tests that pin this
  behaviour are part of the change, not a follow-up.
- Yield order stops being deterministic. Pages come back as they finish rather
  than in frontier order, so two runs of the same scan can report the same
  addresses in a different sequence. Nothing in the exports or the session store
  depends on order.
- The tier badge in the control panel stops overstating what the app does.
- Three defects from the same audit are untouched and stay open: the unbounded
  subdomain probe in `_verify_subdomains`, `max_seeds` truncation discarding the
  scored contact pages before they are seeded, and fetch failures being swallowed
  with no `on_blocked` for a non-2xx. The last of those was caught in the act
  during the measurement above: `www.bhp.com` answers 403 from Akamai and
  disappeared silently, along with two other seeds, so the crawl spent its whole
  budget on dev and QA subdomains that Certificate Transparency happened to list.
  It gets its own decision.

## Alternatives considered
- **Stay serial and lower the caps to what is reachable**, around 200 to 400
  pages. Cheap, honest, and no concurrency risk at all. Rejected because it
  accepts reading a few hundred pages of a large municipal site and calling the
  result a scan of it, and because it leaves the declared tier concurrency
  describing nothing.
- **Bound the crawl by wall clock instead of by pages.** Closest to how a scan
  actually ends today, since time is the real limiter. Rejected as the largest
  change of the three and because it makes a run non-reproducible: the same scan
  on the same site returns a different set of pages depending on how the network
  behaved that minute.
- **Expose the whole tier profile in the GUI** - concurrency, delay and page cap
  all editable. The most control, and it would make the page cap something the
  user can spend once the crawl is parallel. Rejected because a badly set trio
  can hammer a site or run for an hour, and because two of the three numbers are
  not the ones being fixed here.
- **A settings file or `RADARCL_*` environment variables, with no GUI control.**
  Cheapest to build and nothing new on screen. Rejected because it is invisible
  to anyone who has not read the documentation, which is most of the GUI's
  audience, and the CLI already serves the reader who has.
