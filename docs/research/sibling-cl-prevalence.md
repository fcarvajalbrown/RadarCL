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

*Results are appended below this line once the run completes. Nothing
above it is edited afterwards.*
