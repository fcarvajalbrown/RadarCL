# 0023 - A wall is not an empty site

## Status
Accepted

## Date
2026-08-05

## Deciders
Felipe Carvajal Brown

## Context
`aprimin.cl` publishes `aprimin@aprimin.cl`, findable in a Google search.
RadarCL scanned it and reported `0 correos encontrados`, then exited in a few
seconds. Nothing in that output said anything had gone wrong.

Measured on 2026-08-05, one GET each:

| Request | Result |
|---|---|
| `https://www.aprimin.cl`, RadarCL's user agent | 202, 169 bytes |
| Same, Chrome 126 user agent with `Accept` and `Accept-Language` | 202, 169 bytes |
| `/.well-known/sgcaptcha/?r=%2F` | 200, 11783 bytes, title `Robot Challenge Screen` |
| Retry after fetching the challenge page | 202, 169 bytes, no cookie issued |

The 169-byte body is the whole of it:

```html
<html><head><link rel="icon" href="data:;"><meta http-equiv="refresh"
content="0;/.well-known/sgcaptcha/?r=%2F&y=ipc:..."></meta></head></html>
```

This is SiteGround's `sgcaptcha`, served by nginx. The challenge page runs a
proof-of-work in a Blob-constructed Web Worker and issues no cookie without it,
so no HTTP client passes it. Changing the user agent does nothing; the site is
not refusing RadarCL's identity, it is refusing everything that cannot run
JavaScript. Google holds the address because search engine crawlers are let
through that wall, and what a search returns is a cached copy of a page RadarCL
is never served.

**The blindness is in RadarCL, not in the wall.** Three failures compounded:

- `202` is a success code, so `Crawler._fetch`'s `raise_for_status()` passes the
  stub through as a good page.
- The stub's only `href` is `data:;`, which `_extract_links` correctly drops for
  having no http scheme, so the frontier empties after the seeds and the crawl
  ends. The instant exit is a symptom of the wall, not a separate bug.
- `extract_emails` finds nothing in 169 bytes of `<head>`, and `cli.py` reports
  the count of what was found without ever asking whether anything was read.

RadarCL already refuses this inference everywhere else it fetches. A resolver
that cannot answer yields UNKNOWN rather than INVALID
([ADR-0009](0009-mx-resolution-failure-is-unknown.md)). A `550 5.7.1` is a fact
about the sender, not the mailbox
([ADR-0017](0017-a-reply-is-evidence-only-about-its-subject.md)). An empty
`evidence` tuple means the page was checked and showed nothing, and its absence
means nobody looked, and consumers are forbidden from reading the two alike
([ADR-0014](0014-country-is-never-inferred-from-a-com-address.md)). The crawler
is the one layer that does not hold the line: a site that would not open and a
site with no addresses produce the same number.

## Decision
**A page that could not be read is reported as unread, never counted as a page
with no addresses.**

Detection is by shape, not by vendor. A response is blocked when it arrives 2xx,
carries no readable text, and offers no followable http link, in a body small
enough that there is nothing else it could be. That test is about what the
response *is*, so it fires on a vendor nobody here has seen, which is the
failure mode this ADR exists to prevent: the signature list that would have
caught `aprimin.cl` today is the same list that misses the next site silently.

**A signature list supplies the vendor name, and only the name.** Recognising
SiteGround's `sgcaptcha` path or Cloudflare's challenge markers turns
`no se pudo leer` into `bloqueado por un desafio anti-bot (SiteGround)`. A
signature never promotes a page to blocked on its own and never rescues one the
shape test rejected, so the list can rot without changing which pages are
detected - it only makes a correct verdict more useful.

**A scan where nothing was readable says so instead of reporting zero.** The
count of addresses found is not a finding when the count of pages read is zero,
and the run summary must distinguish the two, in the CLI and in the GUI alike.
Per the standing language rule, that text ships in Spanish.

**The detector is a parser, so it carries no threshold.** It reads bytes the
crawler has already fetched, cannot fire on a site that is not walled, and
costs nothing per scan that is not recovered - the distinction
[ADR-0022](0022-a-parser-is-not-a-source-and-does-not-need-a-gate.md) drew
between a source, which spends per scan and needs a gate, and a parser, which
does not.

**Getting through a wall is a separate decision, deliberately not taken here.**
It requires a headless browser, which is a real per-install expenditure against
[ADR-0008](0008-vendored-core-dependencies.md)'s offline vendored model and
[ADR-0005](0005-hardware-aware-auto-tuning.md)'s low-spec target, so it is
source-shaped and does need a gate. **How often `.cl` sites are walled has not
been measured**, and no threshold is pre-registered in this ADR because setting
one before knowing what is being decided is the invention ADR-0022 refused.
That measurement, its threshold and its verdict get their own ADR.

## Consequences
- A walled site stops producing a silent zero. `aprimin.cl` is the first known
  case; how many others there are is exactly the unmeasured quantity above.
- **The shape test can call a legitimately empty page blocked.** A redirect stub
  or a JavaScript-only shell that ships no server-rendered content matches the
  same description. That is accepted deliberately: both are pages RadarCL could
  not read, and reporting them as unread is true of both. What is lost is the
  ability to say which, and the vendor name is what fills that in when it can.
- **A JavaScript-only site is now reported honestly rather than invisibly**, as
  a side effect. This is the same gap ADR-0021 recorded for stylesheet-applied
  hiding and ADR-0022 for script-constructed addresses, and it still has the
  same answer, still deferred: a headless browser.
- The crawler gains a reason to look at a response beyond its status code, which
  is new. It still does not parse for meaning - the test is length, text
  presence and link presence, not content.
- No new dependency.
- The v0.6.0 release, currently cut and unshipped, is where this lands or does
  not; that sequencing is a separate call.

## Alternatives considered
- **Vendor signatures only** - match `sgcaptcha`, Cloudflare's `cf-mitigated`
  header, the `Just a moment` title, and nothing else. Zero false positives on
  thin pages, and it would have caught `aprimin.cl` exactly. Rejected because
  the failure being fixed is a silent zero, and a signature list reproduces it
  in full for every vendor not on the list. A detector that only sees what it
  was told about leaves the same hole one vendor later, and gives no signal that
  it is doing so.
- **Report unreadable generically, with no vendor diagnosis at all.** Honest,
  no list to maintain, no risk of naming the wrong vendor. Rejected because the
  vendor name is what tells the reader whether a second attempt is worth
  anything: a proof-of-work wall and a broken page are the same message under
  this option and call for opposite responses.
- **Treat 202 as a failure status in `_fetch`.** Would have caught this one
  case. Rejected as a coincidence fix - the status code is not what makes the
  response unreadable, and a wall served as 200 would sail straight through.
- **Follow the meta-refresh and solve the challenge.** Rejected here as the
  separate, gated decision described above, not as an idea.
- **Do nothing and note that `aprimin.cl` is unreachable.** Rejected because the
  defect is not that one site is walled, it is that RadarCL asserts an absence
  it never observed. Every other layer of this tool refuses that inference.
