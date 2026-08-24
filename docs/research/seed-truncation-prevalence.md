# How often does `max_seeds` truncation discard a scored contact page?

Research notes for the third of the four crawl defects listed in
[CLAUDE.md](../../CLAUDE.md), the one where `discover_seeds` fills the seed
list with live subdomain roots before the semantic stage contributes a single
scored page, then cuts to `max_seeds`.

**This file is a pre-registration.** It was written and committed before the
measurement ran. The frames below were constructed first, because their counts
are part of the design; not one domain in either sample had been probed when
this was committed. That ordering is what stops the thresholds being chosen to
fit a result, and it is the discipline
[sibling-cl-prevalence.md](sibling-cl-prevalence.md) set for this repository.

Dated 2026-08-23.

## The mechanism

`discover_seeds` in `app/core/seed_discoverer.py` runs four stages and appends
their output to one list:

| Stage | What it adds |
|---|---|
| 1-2 | Certificate Transparency names, DNS-verified, as bare roots |
| 3 | internal links scored for email-hunting relevance, best first |
| 4 | DuckDuckGo results |

It then returns `seeds[:max_seeds]`, with `max_seeds` defaulting to 20. Stage 2
runs before stage 3, so a domain with 20 or more live subdomain roots consumes
every slot and no scored page is ever seeded. Stage 3 is the only stage that
finds a `/contacto` or a `/nuestro-equipo` page, which is where addresses live.

This is the failure [ADR-0013](../adr/0013-curated-source-stage-removed-after-measurement.md)
recorded for the curated-source stage, in a different stage.

## Why a new measurement

A pilot on three domains was run first and is reported here because it is what
prompted the study, not because it decides anything:

| Domain | live roots | scored links | Fires? |
|---|---|---|---|
| `bhp.com` | 66 | 0 | no, nothing to lose |
| `gecamin.com` | 5 | 6 | no |
| `nunoa.cl` | 3 | 64 | no |

n=3 cannot support a decision, and Felipe rejected it as a basis on those
grounds. The mechanism is provable by reading the code; what is unknown is how
often the conditions co-occur on domains a user would actually name.

## Populations

The quantity is a property of a **domain**, not of an organisation. Seed
discovery consumes a domain and nothing else, so the unit is a domain a RadarCL
user could plausibly type.

This matters because a website domain is not a mail domain. A Chilean news site
publishes at `emol.com` while its addresses sit on a different domain
altogether. That is a limit of what the study can claim, stated here rather
than discovered later: the measurement describes seed discovery for the domain
named, and says nothing about where any organisation's mail lives.

It also rules out substitution. Replacing a recorded host with the one that
looks like the organisation's "real" domain requires knowing each organisation,
which puts the researcher's own recall inside the frame - the reason
[sibling-cl-prevalence.md](sibling-cl-prevalence.md) rejected CMF and the Bolsa
as frames. **No host is substituted for another anywhere in this study.**

### Frame A - Chilean organisations publishing on `.cl`

Wikidata entities with `P17` (country) = `Q298` (Chile) and `P856` (official
website), constructed live on 2026-08-23:

| Step | Count |
|---|---|
| rows returned | 3647 |
| distinct entities | 3396 |
| **with at least one `.cl` website - frame A** | **2753** |
| with no `.cl` website at all - frame B | 643 |

Where an entity lists more than one `.cl` website, the alphabetically first
host is taken. A rule, not a preference.

### Frame B - Chilean organisations on a non-`.cl` domain

The 643 above. This population exists in the study because
[ADR-0024](../adr/0024-scope-follows-the-target-domain.md) has just made these
domains scannable, so they are targets now in a way they were not in July, and
because their subdomain structure has no reason to resemble frame A's.

## Sampling

- **Frame A: n = 400**, drawn by shuffling the sorted frame with
  `random.Random(20260823)` and screening in order until 400 eligible distinct
  domains accumulated. 597 entities were screened to get there. The seed is
  recorded so the draw reproduces.
- **Frame B: census, 643 entities screened, 306 distinct domains.** No sampling
  error at all; the only question is how far the frame generalises.

Screening happens after the draw rather than before it, which departs from
`sibling-cl-prevalence.md`. The reason is mechanical: Wikidata's own query
service returns 504 on the `P31/P279*` walk in batches above about fifty, and
429 under sustained use, so classifying all 2753 entities up front is not
available. Shuffle-then-screen is the same sample; the screening rate is
reported above rather than hidden.

**Eligibility, applied in this order:**

1. `P31/P279*` reaches `Q43229` (organisation).
2. Not `P31/P279*` reaching `Q3917681` (diplomatic mission). A sending state's
   organ sitting in Santiago is not a Chilean organisation.
3. Registrable domain is not a multi-tenant hosting platform. The list is fixed
   in advance: `blogspot.cl`, `webnode.cl`, `comunatransparente.cl`,
   `blogspot.com`, `wordpress.com`, `wixsite.com`, `facebook.com`. A
   certificate name under one of these belongs to the platform, not to the
   unit. **3 excluded from frame A, 12 from frame B.**
4. Domain not already drawn.

A leading `www.` label is stripped. Nothing else about a host is changed.

**On the class queries.** After Wikidata's endpoint began rate-limiting, the
remaining classification ran against QLever's public Wikidata endpoint. The two
were cross-checked on 200 entities already classified by the first: 137
organisations under each, **zero disagreements**. Same data, different engine.

## Biases accepted, and why

- **Notability.** Wikidata covers organisations somebody made an item for, so
  the frames skew large and well-known. That skew runs *toward* the condition
  being measured, since a large organisation has more subdomains, so the rate
  reported here should be read as an upper bound for the general case.
- **`P17` conflates "is Chilean" with "is in Chile".** Frame B in particular
  mixes Chilean organisations with Chilean arms of foreign firms. Recorded as a
  limit; the same limit `sibling-cl-prevalence.md` recorded and could not fix.
- **Diplomatic-mission removal is imperfect.** A representative office that
  Wikidata does not class under `Q3917681` survives the screen. Frame B's draw
  contains at least one.
- **A website domain is not a mail domain**, as above.

## What counts as an answer

Per domain, running the real `app/core/seed_discoverer` internals, no
reimplementation:

| Field | Meaning |
|---|---|
| `ct_names` | certificate names, plus the bare domain and `www.` |
| `live_roots` | of those, DNS-verified and answering |
| `scored_links` | stage 3's output across the first ten live roots |
| `scores` | the score of each, so the discarded tail can be described |
| `duckduckgo` | stage 4's output |
| `scored_lost` | scored links with no slot at `max_seeds = 20` |
| `fires` | `live_roots >= 20` **and** `scored_links > 0` |
| `resolves` | whether anything at the domain answered at all |

A domain where nothing resolves cannot fire, and would drag the rate down while
saying nothing about seed discovery. **Both rates are reported** - over all
drawn units, and over units that resolve - and the count of non-resolvers is
stated. Neither is chosen after seeing the numbers: the rate over resolving
units is the primary, declared here.

Frame B units additionally record whether `<base>.cl` has an MX, through
`app.core.dns_lookup.resolve_mx`. That is context for reading frame B, not an
input to any decision, and [ADR-0019](../adr/0019-the-sibling-cl-hint-is-measured-and-declined.md)
has already declined to act on that signal.

## The A/B arm

`scored_lost` counts pages, and pages are a proxy. The thing that matters is
addresses. So every domain that fires is crawled twice, with the same page cap,
delay and concurrency, differing only in the seed list:

- **current order**: roots, then scored links, cut at 20.
- **reserved order**: half of `max_seeds` reserved for the top-scoring links,
  the rest filled with roots, and either side's unused slots handed to the
  other.

Reported: addresses found by each, and the set difference in both directions.
The arm can show the fix recovering nothing, which is the outcome it exists to
make possible.

## Decision rule, fixed in advance

Felipe's, taken on 2026-08-23 before any domain was measured. The seed ordering
is changed only if **both** hold in frame A:

1. the lower bound of the 95% interval on the firing rate, over resolving
   units, is above **5%**; and
2. the median `scored_lost` among firing domains is at least **5**.

At n=400 the worst-case 95% half-width is 4.9 points, and about 2.9 points near
a rate of 10%, so condition 1 is decidable at this sample size rather than
merely reportable.

Frame B is reported separately and does not enter the rule. Pooling a census of
one population with a sample of another produces a number that describes
neither.

**One thing is not yet decided and is not a rule here.** If the A/B arm
recovers zero additional addresses across every firing domain, that arguably
overrides both conditions above. It is written down as an open question rather
than applied, because the decision is Felipe's and he has not made it.

## Run 1, 2026-08-23: void

The first run measured all 706 units and produced nothing usable. It is kept
here because a pre-registered study that quietly re-runs after a failure is no
longer pre-registered.

**Certificate Transparency was unavailable for 389 of 400 units in frame A and
304 of 306 in frame B.** `_ct_subdomains` raised `CTUnavailable` on 97% of the
sample, so `live_roots` collapsed to the bare domain and its `www` - a median
of 2 across both frames, against a firing threshold of 20. The headline result,
0 firing domains in frame A, is a fact about a dead data source and not about
seed truncation.

The cause was this study's own volume. Checked immediately afterwards:

| Source | Response |
|---|---|
| `crt.sh` | 502 Bad Gateway |
| `api.certspotter.com` | 429 `rate_limited`, per-day quota for unauthenticated use |

The pilot retrieved 125 certificate names for `bhp.com` earlier the same day, so
CT was answering before the run and not after it. 706 domains in one pass, each
querying crt.sh and falling through to CertSpotter, exhausted the daily
allowance.

Two things this run did establish, neither of them the question asked:

- **Recording `ct_available` per unit is what caught it.** Without that field
  the run would have reported a clean 0% with a tight interval, and the number
  would have looked like an answer.
- **A scan whose CT lookup fails says nothing about it.** `discover_seeds`
  catches `CTUnavailable` and continues on the bare domain
  ([ADR-0011](../adr/0011-ct-fallback-and-source-hygiene.md)), and no message
  reaches the user. That is the shape ADR-0023 refused for bot walls, in the
  seed stage, and it is a separate defect from the four already listed.

Run 2 needs a pacing and caching strategy, and possibly an authenticated
CertSpotter key. Neither is decided here.

## Run 2, 2026-08-24: blocked, not started

Blocked on `crt.sh`, which has answered 502 for over a day. The study cannot
run without it, and the reason is a measured ceiling rather than an estimate.

Fifteen consecutive full-domain queries were sent to CertSpotter with a free
API key:

| Queries | Result |
|---|---|
| 1-10 | 200 |
| 11-15 | 429 |

Exactly ten, then refused. SSLMate's published free tier is 10 full-domain
queries an hour **with or without an account**, and
`_certspotter_subdomains`'s own docstring already recorded the unauthenticated
figure. An API key was obtained before this was checked and buys nothing here;
`include_subdomains=true` is a full-domain query, and the 100/hour allowance
applies to single-hostname queries, which cannot enumerate subdomains and so
cannot answer this study's question.

At 10 an hour, the 706 units need about 71 hours of wall clock. Frame A alone
would need ten. Both are dominated by simply waiting for the source that has no
cap, which is the reason
[ADR-0011](../adr/0011-ct-fallback-and-source-hygiene.md) puts crt.sh first.

**State preserved for whoever picks this up:** the frames, the draw, the seed,
the eligibility rules and the decision thresholds are all committed above and do
not need redoing. Ten domains are already in the CT cache. The measurement
script reads certificate names from that cache only and can no longer make a
live CT call, so resuming cannot re-burn a quota. Nothing here needs redeciding;
it needs crt.sh answering.

## What this does not decide

Whether to reserve slots is one question. How many to reserve is another, and
the score distribution recorded above is input to it, not an answer. The
resulting ADR covers only what the numbers support.
