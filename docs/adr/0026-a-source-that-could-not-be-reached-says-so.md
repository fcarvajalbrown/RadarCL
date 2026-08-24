# 0026 - A source that could not be reached says so

## Status
Accepted. Extends [0011](0011-ct-fallback-and-source-hygiene.md); the cascade
it decided is unchanged and reaffirmed below.

## Date
2026-08-24

## Deciders
Felipe Carvajal Brown

## Context
[ADR-0011](0011-ct-fallback-and-source-hygiene.md) decided that a Certificate
Transparency source answering with no records has answered, that only an
all-sources failure raises `CTUnavailable`, and that `discover_seeds` catches it
so the next stage still runs. All of that was right and none of it changes here.

What it did not decide is whether the user is told. Nobody is. `discover_seeds`
catches `CTUnavailable`, continues on the bare domain and its `www`, and the
scan reports a seed count as though nothing happened.

This stopped being hypothetical on 2026-08-23. A 706-domain measurement raised
`CTUnavailable` on **693 of them** - 389 of 400 in one sample, 304 of 306 in
the other - and reported a clean result that was an artefact of a dead source.
The measurement caught it only because it recorded source availability per unit;
a scan does not, so a user gets the artefact with no way to see it.

The conditions behind that were checked rather than assumed:

| Source | State, 2026-08-23 to 24 |
|---|---|
| `crt.sh` | HTTP 502 for over a day, then 404 |
| `api.certspotter.com` | 10 full-domain queries an hour, measured as 10 × 200 then 5 × 429 |

Ten an hour holds with or without a free API key, because
`include_subdomains=true` makes it a full-domain query and the larger allowance
is for single-hostname queries. So a source being unavailable is a normal
operating condition, not a rare one.

**What the user sees is the same either way.** Seed discovery for `uchile.cl`,
run twice within minutes, differing only in whether CT answered:

| | Seeds | Composition | Shared with the other run |
|---|---|---|---|
| CT available | 20 | 18 subdomain roots | 2 |
| CT unavailable | 20 | 2 roots, 18 scored contact pages | 2 |

Two scans sharing two seeds out of twenty, and both printing
`20 semillas encontradas`. The semantic stage backfills the empty slots, so
even the count is identical. On `nunoa.cl` the difference is a single seed and
the count is likewise unchanged.

This is the shape [ADR-0023](0023-a-wall-is-not-an-empty-site.md) refused for
bot walls, one stage earlier: an absence nobody observed, reported as a finding.
It is also the shape [ADR-0009](0009-mx-resolution-failure-is-unknown.md) refused
for DNS, where a resolver that could not answer is not evidence an address is
dead.

## Decision
**The cascade stands; the silence goes.** When every Certificate Transparency
source fails, `discover_seeds` still continues on the bare domain, exactly as
ADR-0011 decided. It additionally reports that the stage could not run, and the
CLI and the GUI both say so.

**The wording lives beside the failure, not in each caller**, the way
`describe_walls` and `describe_off_target` already do, so the CLI and the GUI
cannot drift into saying different things about the same event.

**The message names what is missing, not what failed.** A user does not need to
know which of two certificate logs returned which status code; they need to know
the result does not cover subdomains. The reason string stays available for the
debug feed.

**A source with no records still says nothing.** ADR-0011's distinction is the
load-bearing one here: a source that answered "no certificates" has answered,
and a scan of a domain that genuinely has no subdomains must not grow a caveat
it has no reason to carry. Only an all-sources failure is reported.

## Consequences
- A degraded scan becomes distinguishable from a healthy one. Today they are
  not, and the seed count is identical in both, which is worse than a smaller
  number would have been.
- **A transient outage now adds a line to an otherwise clean run.** That is the
  cost, and it is the same cost ADR-0023 accepted for walls. It is bounded by
  the rule above: no message when a source answered with no records.
- The user cannot act on the message beyond re-running later, which is a real
  limit. It is still worth saying, because the alternative is a result that
  silently means something different from what it appears to mean.
- Seed discovery's timing is unchanged. No retry is added here, so a scan does
  not get slower when a source is down.
- `discover_seeds` grows a callback parameter, so its signature changes for
  every caller. `app/cli.py` and the seed-discovery worker both pass one; the
  tests that call it directly do not have to.
- The measurement parked in
  [seed-truncation-prevalence.md](../research/seed-truncation-prevalence.md)
  needs this distinction anyway, and records it per unit today with its own
  field. The two are the same judgement made in two places, which is one place
  too many, but the research script must keep working against released versions.

## Alternatives considered
- **Retry with backoff, then report.** crt.sh outages are usually temporary and
  CertSpotter's 429 is a rolling hourly bucket, so spaced retries would often
  convert a failure into an answer. Rejected because it makes seed discovery
  take minutes with nothing on screen explaining the wait, and because the
  reporting decided here is what makes a retry policy measurable later. It
  remains open, and it is a separate decision.
- **Refuse the scan outright** when the subdomain stage cannot run. Impossible
  to misread, and defensible on a target like `uchile.cl` where the seed lists
  overlap by two. Rejected because on `nunoa.cl` the loss is one seed in twenty,
  and turning that into no result at all serves nobody.
- **Leave it silent.** ADR-0011's reasoning for the silent cascade still holds
  for the cascade itself. Rejected because that reasoning is about which stage
  runs next, not about what the user is told, and the two questions were
  conflated.
