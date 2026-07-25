# 0019 - The sibling `.cl` hint is measured and declined

## Status
Accepted

## Date
2026-07-25

## Deciders
Felipe Carvajal Brown

## Context
[ADR-0018](0018-generation-stays-in-cl-and-a-guess-says-so.md) held pattern
generation to `.cl` in both directions, and named the gap that left in its own
Consequences: *"RadarCL does not tell the user that `riotinto.cl` exists when
they ask for `riotinto.com`. The measurement says that hint would help on eight
of thirteen companies. It is not built here, and it is the obvious next
thing."* [ROADMAP.md](../../ROADMAP.md) carried it as v0.60 item 1.

ADR-0018 also said plainly what was wrong with its own evidence: *"The sample
is thirteen companies chosen because they came up in earlier measurements, not
drawn at random. It is enough to show the `.cl` mail domain is common, not
enough to put a number on how common."* At n=13, 8/13 carries a 95% interval of
roughly ±26 points.

**A threshold was committed before any measurement ran.** The frame, the seed,
the sample size and the ship gate went into
[docs/research/sibling-cl-prevalence.md](../research/sibling-cl-prevalence.md)
in commit `13ab465`, before the first DNS query was sent. The gate: ship only
if the 95% Wilson interval's lower bound reaches 40%. The reasoning recorded
at the time was that the hint's whole value is the claim that a sibling
*usually* exists, and a line that is right fewer than two times in five is one
the user learns to scroll past.

**Population (a)**, 200 domains drawn with `random.Random(20260725)` from a
Wikidata frame of 334 Chilean organisations holding a non-`.cl` primary domain,
diplomatic missions excluded on a stated rule:

| | |
|---|---|
| Distinct sibling `.cl` domains | 189 |
| Mail-capable | 84 |
| No mail, definitive | 94 |
| Unreachable | 11 (5.8%) |

**84 of 178 reachable = 47.2%, 95% Wilson [39.994%, 54.507%].** The gate is
missed by 0.006 percentage points.

**That margin is not what decides this.** `resolve_mx` implements RFC 5321's
implicit MX, so a domain publishing no MX record resolves to its own A record
and counts as mail-capable. Squatted and defensively-registered domains are
overwhelmingly parking pages, and a parking page has an A record. Checked per
domain, **26 of the 84 have no MX record at all** - `facebook.cl`,
`columbia.cl`, `roche.cl`, `sonda.cl`, `arica.cl`, `skyairline.cl` among them.

**Requiring a real MX record gives 58 of 178 = 32.6%, 95% Wilson
[26.1%, 39.8%]**, an interval lying entirely below the gate. The hint does not
fail by a rounding error. It fails once it has to mean what it says, and the
47.2% is reached only by counting domains that would bounce every message sent
to them.

That `sonda.cl` is implicit-only here, while ADR-0018 lists Sonda among the
companies with *no* `.cl` mail domain, says that pilot was already applying the
strict reading without naming it.

**Population (b)**, a census of Consejo Minero's 9 non-`.cl` member domains
read live from the association's own membership page, points the other way:
**6 of 8 reachable = 75%, [40.9%, 92.9%], every one with a real MX record.**
Eight of the eighteen members already publish on `.cl` and were excluded, since
the hint could never fire for them.

So the two populations genuinely differ, and ADR-0018's 8 of 13 was not wrong
so much as drawn from the corporate one. **A sibling `.cl` mail domain is
normal among large Chilean corporates and uncommon across Chilean organisations
generally.** RadarCL cannot know which of the two a user is pointing at.

Non-response biases toward *understating* prevalence: the eleven unreachable
names are short and commercially valuable, while a domain that does not exist
answers NXDOMAIN quickly and lands in the definitive column. Counting every one
of them as mail-capable gives a ceiling of 95 of 189 = 50.3%, lower bound
43.2% - and that most-favourable-possible resolution still leaves the strict
number far short.

## Decision
**The hint is not built, and v0.60 item 1 closes as measured and declined.**

The gate was committed in advance precisely so that it would bind when the
result was inconvenient, and this is the first time it has bitten. A threshold
that yields the first time it costs something was decoration. This follows
[ADR-0013](0013-curated-source-stage-removed-after-measurement.md), where a
source that sounded obvious was measured at zero and deleted rather than
maintained; the difference is only that this feature is being declined before
it exists rather than after.

**The version ships the measurement instead of the feature.** The frame, the
seed, the sample, the intervals, the non-response and the cost are the
deliverable, in
[docs/research/sibling-cl-prevalence.md](../research/sibling-cl-prevalence.md),
along with the instrumentation in `scripts/sibling_cl_measure.py` and the two
drawn samples in `scripts/data/` so the run reproduces.

**No code implements the hint**, in the CLI, the GUI or `app/core/`. Nothing is
left behind a flag: an unreachable code path is a maintenance cost that carries
a claim nobody measured, which is the shape ADR-0015 removed the Stage 4
placeholder for.

**What would reopen it is named rather than left implicit.** A hint restricted
to targets a user has said are corporate, or a population pre-registered as
"organisations a RadarCL user would actually target" rather than as "Chilean
organisations in Wikidata", could clear a gate honestly. Neither is designed
here, and neither is a roadmap item, because putting one there would promise
work nobody has committed to - the same reasoning ADR-0013 applied to
target-parameterised query URLs.

**The strict reading is the correct one and is recorded for whoever revisits
this.** If the hint is ever built, "mail-capable" must mean a published MX
record. The implicit-MX fallback is how `facebook.cl` became a positive.

## Consequences
- RadarCL still says nothing when a user targets `riotinto.com`, and after
  ADR-0018 that user gets no output at all. The gap ADR-0018 named stays open,
  now with a number attached to how often filling it would have helped.
- **ADR-0018's "eight of thirteen" should not be quoted as prevalence again.**
  It is accurate for the corporate population it sampled and roughly matches
  this ADR's 75% there. It is not the rate across Chilean organisations, which
  is 47.2% loosely and 32.6% strictly.
- **ADR-0017's "Microsoft 365 carries 12 of 20" does not generalise.** On a
  random draw of 58 domains with real MX records: 47% self-hosted, 29% Google,
  22% Microsoft 365. Google leads Microsoft and neither reaches half. That ADR's
  catch-all reasoning is untouched; only the incidental provider observation is.
- **A defect was found in `dns_lookup.py` while measuring the cost**, and fixed
  separately in `ef4a7d2`. `_PUBLIC_NAMESERVERS` lists Google and Cloudflare and
  Cloudflare had never been consulted: dnspython's `lifetime` bounds the whole
  question rather than each server, so the first server's timeout exhausted the
  budget. No ADR, because ADR-0009 already decided the fallback transports
  exist and this makes the code do what it says. It is recorded here because the
  cost measurement is what surfaced it, and because a redundancy that never
  fires is exactly the kind of thing that stays hidden while everything appears
  to work.
- **ROADMAP.md's EUIPO figure was wrong and is corrected.** It read
  "cybersquatting at 49% of major brands with 26% of squatted domains on
  ccTLDs". The study reports 486 of 993 analysed brand-related *domain names*
  (49%) judged suspicious across 20 brands of small, medium and large entities,
  and 26% is the ccTLD share of all analysed domains rather than of the
  suspicious ones. The on-point figure is that 116 of 257 brand-related ccTLD
  domains, 45%, were suspicious.
- The offline suite is unchanged by this decision. It gained one test from the
  nameserver fix, 149 to 150.
- `scripts/data/` is a new directory holding the drawn samples and a cached
  Public Suffix List. It is instrumentation, not shipped code, and nothing in
  `app/` imports it.
- **A future agent will read v0.60 item 1 and see it checked with no feature
  behind it.** The roadmap says why in the item itself rather than only here,
  since that is the document read first.

## Alternatives considered
- **Ship it anyway, recording that the gate was missed by 0.006pp**, on the
  grounds that one cached DNS query costs almost nothing and the point estimate
  is 47%. Rejected: the override is defensible on cost and indefensible on
  precedent, since a pre-registration that yields the first time it binds makes
  every future one advisory. The strict number also removes the "it was
  basically 40%" framing - honestly measured, this is 32.6%.
- **Ship it restricted to a real MX record**, so it could never point at
  `facebook.cl`. More accurate, and it misses the gate by more rather than less,
  so it is an override too. Kept in the record as the shape the feature should
  take if it is ever revisited.
- **Re-scope and re-measure**, pre-registering a narrower population of
  organisations a RadarCL user would actually target rather than all Chilean
  organisations in Wikidata. The most rigorous answer and the one that might
  well pass, since population (b) is 75%. Rejected for now as a cost decision
  rather than a principle: it is another full measurement cycle before any code
  exists, and the item is not blocking anything.
- **Treat population (b) as the real population** and ship on its 75%.
  Rejected outright: the gate was pre-registered on (a), and choosing which
  population counts after seeing which one passed is exactly the failure
  ADR-0012 records and this whole exercise was built to avoid.
- **Widen the sample beyond n=200.** n=384 would have given ±5.0 points instead
  of ±6.9. Rejected because the strict interval misses by more than any
  plausible width correction, so more domains would sharpen a number that has
  already answered the question.
- **Keep the hint behind an off-by-default flag** rather than deleting it
  unwritten. Rejected on ADR-0015's reasoning about the Stage 4 placeholder: an
  interface nobody exercises still makes a claim, and this one's claim has been
  measured as wrong two times in three.
