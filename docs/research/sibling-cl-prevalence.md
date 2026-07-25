# How often does a non-`.cl` organisation run a mail-capable `<base>.cl`?

Research notes for [ROADMAP.md](../../ROADMAP.md)'s v0.60 item 1, the
sibling `.cl` mail-domain hint.

**This half of the file is a pre-registration.** It was written and
committed before a single DNS query was sent, so the threshold below
cannot have been chosen to fit a result. That is the whole point of it.
[ADR-0012](../adr/0012-curated-sources-assert-identity.md) is what happens
otherwise: a stage that sounded right, shipped, and was deleted a version
later once somebody asked what it returned.

Dated 2026-07-25.

## Why a new measurement

Three numbers currently circulate in this repository, and all three are
convenience samples reported as prevalence:

| Claim | Where | Sample |
|---|---|---|
| 8 of 13 companies run a mail-capable `<base>.cl` | [ADR-0018](../adr/0018-generation-stays-in-cl-and-a-guess-says-so.md) | 13, chosen because earlier work surfaced them |
| 17% of reachable `.cl` domains are catch-all | [ADR-0017](../adr/0017-a-reply-is-evidence-only-about-its-subject.md) | 20, met while testing something else |
| the `.com` attribution signals | [ADR-0014](../adr/0014-country-is-never-inferred-from-a-com-address.md) | 16 reachable pages |

ADR-0018 says so itself: *"The sample is thirteen companies chosen because
they came up in earlier measurements, not drawn at random. It is enough to
show the `.cl` mail domain is common, not enough to put a number on how
common."* At n=13, 8/13 carries a 95% interval of roughly ±26 points. It is
compatible with a minority and with nearly all, which means it cannot
decide anything.

## Populations

The hint only ever fires when a user targets a **non-`.cl`** domain, so
that is the population: organisations a RadarCL user would plausibly
target which do not already publish on `.cl`. It splits in two, and the
two behave differently enough to be measured apart.

### (a) Chilean organisations on a non-`.cl` primary domain

**Frame: Wikidata.** Entities with `P17` (country) = `Q298` (Chile) and
`P856` (official website), restricted to those whose `P31` is a subclass of
`Q43229` (organization), keeping only those where **no** official website
sits on a `.cl` host.

Chosen because it is the only candidate frame that yields the *domain*
itself. CMF's issuer register, the Bolsa de Santiago listing and the SII
nómina are all keyed by RUT and razón social, so building a domain list
from any of them means hand-resolving each entity, which puts the
researcher's own recall inside the frame. It also closes the one external
route ADR-0014 recorded as *untested* rather than rejected — its query
service refused the requests made then, and answered on this date.

Construction, live on 2026-07-25:

| Step | Count |
|---|---|
| Wikidata entities, country Chile, with a website | 3231 |
| of which organisations (`P31` under `Q43229`) | 2401 |
| of those, no `.cl` website at all | 383 |
| **minus diplomatic missions (`P31` under `Q3917681`)** | **334** |

The 49 diplomatic missions are removed on a stated rule, not by hand.
Wikidata records `country = Chile` for the Swiss embassy in Santiago
because the embassy *sits* in Chile, so `eda.admin.ch` and `mzv.cz` enter
the frame as though they were Chilean organisations. They are the sending
state's organ, so they belong to neither population, and leaving them in
would push the rate down through a mechanism that has nothing to do with
the question.

**Biases accepted, and why:**

- **Notability.** Wikidata covers organisations somebody bothered to
  create an item for, so it skews large and well-known and thins out
  badly among SMEs. Accepted because every alternative frame is *also*
  large-skewed (CMF and the Bolsa are listed companies by construction)
  and additionally needs hand-resolution.
- **`P17` conflates "is Chilean" with "is in Chile".** After removing
  missions, the frame still mixes Chilean-owned organisations with Chilean
  subsidiaries of foreign firms, e.g. `Roche (Chile)` on `roche.com`.
  Splitting them was attempted with `P159` (headquarters) and abandoned:
  it is **missing for 205 of 383**, and 48 of the 49 embassies record a
  headquarters *in Chile*, so the property does not separate what it looks
  like it should. Recorded as a limit rather than papered over.

### (b) Foreign organisations with Chilean operations

**Frame: Consejo Minero's membership, read live from
`consejominero.cl/nosotros/socios/` on 2026-07-25.** Every member produces
over 50,000 tonnes of fine copper a year or the economic equivalent, and
the association states its members account for 94% of Chilean copper
output. Each member's domain is taken from that association's own profile
page for that member, not supplied from memory.

**This is a census, not a sample.** All 18 members are measured, so there
is no sampling error at all; the only question is how far mining
generalises.

Of the 18, **8 already publish on `.cl`** — `cmp.cl`, `aminerals.cl`,
`barrickchile.cl`, `collahuasi.cl`, `elabra.cl`, `goldfields.cl`,
`sgscm.cl`, `kinrosschile.cl` — so the hint could never fire for them and
they are excluded from the denominator. Ten member entries remain on a
non-`.cl` domain, resolving to **9 distinct domains** (BHP and Pampa Norte
share `bhp.com`).

**Bias accepted:** this is the mining sector, which is exactly the sector
most likely to have a long-established Chilean presence, so if anything it
should *overstate* how often a foreign firm runs a Chilean domain. It is
named here rather than discovered later. A general frame of foreign firms
in Chile was not built; AmCham's directory was not confirmed enumerable.

## Sampling

- Population (a): **n = 200** drawn from the 334-entity frame with
  `random.Random(20260725).sample()` over the sorted frame. The seed is
  recorded so the draw reproduces. Where Wikidata lists more than one
  official website for an organisation, the alphabetically first host is
  taken — a rule, not a preference.
- Population (b): **census, n = 9 distinct domains.**

n=200 gives a worst-case 95% half-width of ±6.9 points, at p=0.5. That is
enough to separate "most organisations" from "a minority", which is the
only distinction the decision below turns on. n=384 would buy ±5.0 points,
which no branch of the decision spends.

## What counts as an answer

One MX lookup per domain through `app/core/dns_lookup.resolve_mx`, which
already draws the distinction this measurement needs and is the same code
path the shipped feature would use:

| Outcome | Counted as |
|---|---|
| returns a mail host | sibling exists and is mail-capable |
| `DomainNotFound` | definitive negative — no such domain, or a null MX under RFC 7505 |
| `MXUnavailable` | **non-response**, reported separately, never as a zero |

No SMTP. A DNS answer settles the question, so probing a mail server would
be traffic sent to a third party for nothing.

Non-response is reported as its own count with the direction of its bias
stated, because it is not random: ADR-0014 already measured that roughly a
third of large corporate sites refuse this crawler and that `bhp.com`
closes the connection outright.

## Pre-registered decision rule

**Ship the hint if the 95% confidence interval's lower bound for
population (a) is at or above 40%.**

Wilson interval, since it behaves at proportions near the ends where the
normal approximation does not.

The reasoning, written now rather than afterwards: the hint's entire value
is the claim that a sibling *usually* exists. If it is right fewer than
two times in five, it is a line the user learns to scroll past, and a tool
that cries wolf about a better target is worse than one that says nothing.
Forty per cent is set below a majority deliberately, because the cost side
is genuinely small — one cached DNS query that never blocks a scan — but
it is set high enough that the pre-registration is a real gate rather than
a formality something like 10% would clear automatically.

Population (b) is reported **without a gate**. It is a census of one
sector at n=9, informative about mining and not a basis for a threshold.
If (a) clears 40% and (b) disagrees, both numbers go in the ADR and the
disagreement is the finding.

## Also pre-registered

- **Catch-all prevalence on `.cl`, re-measured on the same footing.**
  ADR-0017's 17% is 3 of 18 domains met while testing something else, and
  that ADR explicitly defers a real measurement. Same discipline: stated
  frame, random draw, reported n, interval and non-response. No threshold
  attaches to it — catch-all detection already ships and this sizes its
  effect rather than deciding its existence.
- **Cost, not only benefit.** Extra DNS queries per scan, added latency at
  median and p95, and behaviour on a machine where UDP/53 is filtered.
  `app/core/dns_lookup.py` exists because that machine is real.

---

*Everything above this line was committed in `13ab465` before the first DNS
query was sent, and has not been edited since. Everything below is the run.*

# Results, 2026-07-25

## The gate was missed

| Population (a) | |
|---|---|
| Domains drawn | 200 |
| Distinct sibling `.cl` domains | 189 (11 hosts shared a sibling) |
| Mail-capable | 84 |
| No mail — definitive | 94 |
| Unreachable — non-response | 11 |

**84 of 178 reachable = 47.2%, 95% Wilson [39.994%, 54.507%].**

The pre-registered rule was a lower bound at or above 40%. It lands at
**39.994%**, missing by 0.006 percentage points.

A margin that small is not a real difference, and it is not what decides
this. The strict analysis below is.

## Thirty-one per cent of the "mail-capable" siblings accept no mail

`resolve_mx` implements RFC 5321's implicit MX: when a domain publishes no
MX record, its A record is treated as the mail exchanger. So a domain with a
web server and no mail service returns a host and counts as mail-capable.

Squatted and defensively-registered domains are overwhelmingly parking
pages, and a parking page has an A record. Checked per domain, **26 of the
84 mail-capable siblings have no MX record at all**:

`roche.cl`, `sonda.cl`, `facebook.cl`, `columbia.cl`, `arica.cl`,
`skyairline.cl`, `frutillar.cl`, `xepelin.cl`, `chicotrujillo.cl`,
`veritrade.cl`, `huilohuilo.cl`, `enelamericas.cl`, `13i.cl` and thirteen
more.

**Requiring a real MX record gives 58 of 178 = 32.6%, 95% Wilson
[26.1%, 39.8%].** The entire interval sits below the gate.

That is the finding. The hint does not fail by a rounding error; it fails
once it has to mean what it says. The 47.2% is reached only by counting
domains that would bounce every message sent to them.

One cross-check that the strict reading is the right one: `sonda.cl` is
implicit-only here, and
[ADR-0018](../adr/0018-generation-stays-in-cl-and-a-guess-says-so.md) lists
Sonda among the companies with *no* `.cl` mail domain. That pilot was
already applying the strict reading without saying so.

## Population (b) clears it, and the two populations really differ

Consejo Minero census, 9 distinct non-`.cl` domains:

| | |
|---|---|
| Mail-capable | 6 |
| No mail | 2 — `bhp.cl`, `south32.cl` |
| Unreachable | 1 — `sqm.cl` |

**6 of 8 reachable = 75%, 95% Wilson [40.9%, 92.9%]**, and **all six have a
real MX record** — no implicit-MX cases at all. This is a census, so there
is no sampling error; the interval reflects only the small denominator.

ADR-0018's 8 of 13 (61.5%) was drawn from large corporates and is consistent
with this, not with population (a). The honest summary is that **a sibling
`.cl` mail domain is normal among large Chilean corporates and uncommon
across Chilean organisations generally.** The hint's value depends entirely
on who it is pointed at, which is not something a tool can know in advance.

## Non-response

| | Unreachable | Share |
|---|---|---|
| (a) | 11 of 189 | 5.8% |
| (b) | 1 of 9 | 11.1% |

Population (a)'s unreachable set is `europa.cl`, `chile.cl`, `latam.cl`,
`ya.cl`, `myspace.cl`, `altia.cl`, `christushealth.cl`, `oneaircharter.cl`,
`trabajosocialchile.cl`, `fundacionneruda.cl`, `ccespana.cl`.

**The bias runs toward understating prevalence.** These are short,
commercially valuable names likely to be registered and in use; a domain
that does not exist answers NXDOMAIN quickly and lands in the definitive
column instead. Counting every unreachable domain as mail-capable, the
ceiling would be 95 of 189 = 50.3%, whose lower bound is 43.2% — so even the
most favourable possible resolution of the non-response does not lift the
strict number anywhere near the gate.

## Two frame defects found during the run, neither of which changes the verdict

**Shared platforms leak through.** `historiasdelorbisterrarum.wordpress.com`
yields the base `wordpress` and so the sibling `wordpress.cl`, which is
nobody's Chilean mail domain. Same for `sites.google.com` → `google.cl` and
`museoszonanortechile.es.tl` → `es.cl`. The frame excluded shared hosting
using the PSL's private section, and `blogspot.com` and `wixsite.com` are in
it while `wordpress.com`, `sites.google.com` and `es.tl` are **not** —
checked against the live list rather than assumed.

Dropping those three siblings gives 82 of 175 = 46.9%, 95% Wilson
[39.61%, 54.24%]. Still a miss, slightly larger.

**Eleven hosts shared a sibling**, e.g. four Neruda foundation entities all
mapping to `fundacionneruda.cl`. Deduplicated by sibling before counting, so
one domain is one observation.

## Cost

- **One MX lookup per scan**, not per address, and only when the target is
  non-`.cl`. Cached per domain for the run, the same stance
  [ADR-0016](../adr/0016-catch-all-domains-are-not-valid.md) takes on
  catch-all.
- **Latency: median 5.07s, p95 7.39s.** Measured on a machine whose system
  resolver does not answer over UDP/53 — the machine
  [ADR-0009](../adr/0009-mx-resolution-failure-is-unknown.md) was written
  for. The 5.07s median is the system-resolver timeout expiring before a
  working transport is reached, not the cost of the answer.
- **On that machine the chain still resolves**, through DNS-over-HTTPS,
  which is exactly what ADR-0009 built it for. 200 domains took 75 minutes
  at one query every 0.5s, all of it waiting.
- These figures were taken **before** the nameserver fix in `ef4a7d2`. Re-run
  over the first 20 siblings on the same machine afterwards:

  | | median | p95 | total |
  |---|---|---|---|
  | before | 5.15s | 9.14s | 111s |
  | after | 3.82s | 7.84s | 92s |

  **Read that as indicative, not as a clean 26%.** The second pass asked for
  the same 20 domains, so upstream resolvers had their answers cached. The
  dominant term is the system resolver expiring rather than the answer
  arriving, and that part does not cache, but the comparison is confounded
  and no attempt was made to unconfound it.

## A defect the cost measurement surfaced

`_PUBLIC_NAMESERVERS` lists Google and Cloudflare, and Cloudflare had never
been consulted. dnspython's `lifetime` bounds the *whole question* rather
than each server, and `_dns_query` set `timeout` and `lifetime` both to 5.0,
so the first server's timeout exhausted the budget and the query raised
before the second was tried.

Verified against `192.0.2.1` (TEST-NET-1, RFC 5737), which by definition
never answers:

| Settings | Result |
|---|---|
| `timeout=5, lifetime=5` (as shipped) | `LifetimeTimeout` at 5.01s, Google never tried |
| `timeout=5, lifetime=15` | resolves at 5.01s |
| after the fix, via `_dns_query` | resolves at 2.52s |

Fixed in `ef4a7d2` by splitting each transport's budget across its
nameservers, which keeps the documented total unchanged. No ADR: ADR-0009
already decided the fallback transports exist, so this makes the code do
what that ADR says.

The DoH leg had been masking it, which is why it survived: the chain still
resolved, one transport later and several seconds slower.

## Catch-all prevalence on `.cl`, re-measured

[ADR-0017](../adr/0017-a-reply-is-evidence-only-about-its-subject.md) records
"17% of reachable ones are catch-all" from 20 domains met while testing
something else, and that ADR defers a real measurement. This is it, on the
same footing as the rest of this file: 60 registrable `.cl` domains drawn with
the same seed from the same Wikidata frame — organisations with country Chile
— with n fixed before the run.

| | |
|---|---|
| Domains probed | 60 |
| Catch-all | 4 |
| Selective | 34 |
| No answer | 21 |
| No such domain | 1 (`miras.cl`) |

**4 of 38 reachable = 10.5%, 95% Wilson [4.2%, 24.1%].**

ADR-0017's 17% sits inside that interval, so the two do not disagree. The new
number is lower, better founded and still imprecise, and the reason it is
still imprecise is the next section.

**Non-response is 35% and it is the dominant limitation.** Eleven domains
timed out and ten dropped the connection (`SMTPServerDisconnected`). Those are
servers refusing an unfamiliar probe rather than networks failing.

**The bias runs toward understating catch-all.** ADR-0016 records that
accept-all is deployed deliberately as an anti-harvesting measure, and the
estates hardened enough to drop an unrecognised SMTP client are the same ones
most likely to be running it. The 21 that would not talk are not a random
sample of the 60.

Two limits of method, stated because they change what the number means:

- **The probe is not the shipped code path.** `verifier._is_catch_all` was
  called directly over one open connection, so this measures "the server
  accepts two invented recipients". ADR-0016 only reaches that question after
  a *real* address returns 250. The server property is the same; the
  population of servers reaching the test is not identical.
- **`miras.cl` does not exist**, and the script files `DomainNotFound` and
  `MXUnavailable` together as unreachable. It is excluded from the
  denominator, which is right — a domain with no mail server has no
  recipient policy — but it is not non-response and is counted separately
  above.

Three of the four catch-all domains are Google-hosted (`smtp.google.com`,
`ASPMX.L.GOOGLE.com`, `aspmx.l.google.com`); the fourth is on
`mail.h-email.net`. The literature ADR-0016 surveyed warned that Microsoft
365 would always look catch-all. In this sample no Microsoft-hosted domain
did, and every catch-all but one was a Google Workspace tenant.

**No threshold was attached to this**, per the pre-registration: catch-all
detection already ships and this sizes its effect rather than deciding
whether it should exist.

## Incidental: who hosts Chilean mail

MX provider of the 58 siblings with a real MX record:

| Provider | Count | Share |
|---|---|---|
| Other / self-hosted | 27 | 47% |
| Google | 17 | 29% |
| Microsoft 365 | 13 | 22% |
| Proofpoint | 1 | 2% |

ADR-0017 recorded "Microsoft 365 carries 12 of 20" from its convenience
sample. On a random draw that does not hold: Google leads Microsoft, and
neither reaches half. Self-hosting is still the largest single category
among these organisations.

## Correction: the EUIPO figure this project has been repeating

ROADMAP.md's v0.60 section says cybersquatting affects "49% of major brands
with 26% of it on ccTLDs". Read against the study itself
([EUIPO, *Focus on Cybersquatting: Monitoring and Analysis*, May 2021](https://euipo.europa.eu/tunnel-web/secure/webdav/guest/document_library/observatory/documents/reports/2021_Cybersquatting_Study/2021_Focus_on_Cybersquatting_Monitoring_and_Analysis_Study_ExSum_en.pdf)),
both halves are wrong:

- The 49% is **486 of 993 analysed brand-related domain names** judged
  suspicious, not 49% of brands. The 20 brands were owned by "small, medium
  and large entities", not major brands.
- The 26% is the **ccTLD share of all 993 analysed domains** (257 of 993),
  not the ccTLD share of the suspicious ones, which is 116 of 486 = 24%.

The figure that actually supports "a name match is not evidence of
ownership" is neither: **116 of 257 brand-related ccTLD domains, 45%, were
suspicious.** That is on point and stronger than the number being quoted.
ROADMAP.md is corrected; this note records what it said before.

## What this measurement cannot say

- **Population (a) and (b) were not separable within one frame.** Wikidata's
  `P159` is missing for 205 of 383, so the Chilean-owned and
  Chilean-subsidiary cases stay mixed in (a). (b) is a separate frame and a
  different sector.
- **(b) is mining.** Nine domains, one industry, the one with the longest
  established Chilean presence. It should if anything overstate.
- **Wikidata's notability bias is real and unquantified here.** Small
  Chilean organisations are underrepresented, and nothing in this run
  measures how far that moves the number.
- **One date, one network.** Every caveat
  [ADR-0014](../adr/0014-country-is-never-inferred-from-a-com-address.md)
  recorded about its own sample applies here too.
