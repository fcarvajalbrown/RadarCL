# 0020 - A convenience sample overstated a source 400 times

## Status
Accepted

## Date
2026-07-25

## Deciders
Felipe Carvajal Brown

## Context
[ROADMAP.md](../../ROADMAP.md)'s v0.60 item 2 proposed a PGP keyserver source
in `seed_discoverer.py`, for direct theHarvester parity and as a plausible fit
for `.cl` institutional contacts who publish keys. The item carried its own
condition: *"Measure recovered addresses per page spent before building the PGP
source."* That condition exists because of
[ADR-0013](0013-curated-source-stage-removed-after-measurement.md).

**The pilot said the source was excellent.** Eight targets, the same list
ADR-0013 used, queried on 2026-07-25:

| Target | ubuntu | MIT |
|---|---|---|
| `uchile.cl` | 12 | **206** |
| `usach.cl` | 15 | 26 |
| `nunoa.cl` | 0 | 0 |
| `providencia.cl` | 0 | 0 |
| `minsal.cl` | 1 | 1 |
| `senado.cl` | 1 | 1 |
| `codelco.cl` | 2 | 6 |
| `entel.cl` | 10 | 13 |

253 addresses from eight requests: about **32 per request**, against the
crawler's best measured yield of 0.65 addresses per page
([ADR-0014](0014-country-is-never-inferred-from-a-com-address.md)'s `nunoa.cl`
control). Roughly fifty times the best page RadarCL crawls.

**The random sample said it was worthless.** A gate was committed in
`6e7326c` before the run: ship if the source recovers at least 0.65 *live*
addresses per request, live meaning not `INVALID` after verification, with
UNKNOWN counting as live per
[ADR-0009](0009-mx-resolution-failure-is-unknown.md). 100 domains drawn with
`random.Random(20260726)` from the 1597 registrable `.cl` domains of Wikidata
organisations with country Chile:

| | Pilot | Random draw |
|---|---|---|
| Addresses per request | ~32 | **0.08** |
| Domains with any keys | 6 of 8 | **7 of 100** |
| Distinct addresses | 253 | **16** |

**0.08 live per request, interval [0.06, 0.08], against a gate of 0.65.**
Missed eightfold.

Every address recovered from a hundred Chilean organisations: nine at
`inacap.cl`, two at `minera.cl`, and one each at `bcn.cl`, `contraloria.cl`,
`senado.cl`, `uda.cl` and `municipalidadillapel.cl`.

**The gap between those two columns is what this ADR is for.** The arithmetic
of the miss is not interesting and nobody would dispute it. What matters is
that the pilot was wrong by a factor of four hundred, and wrong for a reason
that will recur: it used eight targets picked because earlier work had
surfaced them, and two of the eight were universities. Universities are where
PGP keys live. Choosing recognisable targets did not add noise to the estimate,
it moved it two and a half orders of magnitude in one direction.

This happened in the same session, and against the same frame, as
[ADR-0019](0019-the-sibling-cl-hint-is-measured-and-declined.md), which
declined the sibling `.cl` hint after ADR-0018's thirteen hand-picked companies
gave 61.5% and a random draw gave 32.6%. Two features, two convenience samples,
both optimistic, one by a factor of two and one by a factor of four hundred.

Three further findings are recorded because they cost something to obtain.

**Liveness is real but irrelevant.** Fifteen of sixteen addresses were not
INVALID, so 93.8%, [71.7%, 98.9%]. But zero were VALID and fifteen were
UNKNOWN: the honest phrase is *not disproved*, not confirmed. The same servers
that hung up on 35% of the catch-all sample hung up here. At 100% live the
yield is still 0.08.

**`keys.openpgp.org` refuses domain enumeration by policy**, returning 400. Its
[API documentation](https://keys.openpgp.org/about/api) states that lookup by
email takes *"only exact matches"* and *"requires opt-in by the owner of the
email address"*. It was built after the 2019 certificate-poisoning attacks so
the corpus cannot be enumerated. The two servers that do answer are the legacy
SKS network, which is why the addresses are old and why any UID on them is an
unverified claim by whoever uploaded it. `pgp.mit.edu` failed 11 of 100
requests; `keyserver.ubuntu.com` failed none and found 12 of the 16 alone.

**`detect_entity_type` mislabelled every domain in the university bucket.**
`editorialusach.cl` is a publisher, `huachipatofc.cl` a football club,
`supereduc.cl` the schools regulator, and `mguc.cl` is not a university either.
Substring matching on `usach`, `uc` and `educ` does that. So no real university
was drawn, and this run does not test the case the pilot was strongest on.

## Decision
**The PGP keyserver source is not built.** It recovers 0.08 live addresses per
request against a gate of 0.65 committed before the run, and no rescoring of
liveness reaches the bar.

**The record leads on the sampling error, not on the yield.** The number that
should survive this ADR is not 0.08; it is that a convenience sample of eight
recognisable targets overstated a source by four hundred times. ADR-0013
established that a source must be measured before it ships. This establishes
the next thing: *how* it is measured decides the answer, and picking targets
you can name is not measurement. Both of v0.60's features were declined on
random draws that contradicted hand-picked pilots, and the pilots were not
sloppy work — they were the ordinary way anyone would check an idea quickly.

**A pilot is still worth running, and is never a result.** The pilot here was
useful: it established that the endpoints answer, that the parse works, and
what the response shape is. That is what a pilot is for. It becomes a defect
only when its numbers are carried into a decision, which is what would have
happened had the item shipped on the strength of `uchile.cl`.

**The university case is recorded as untested rather than answered.** INACAP
gave 9 of the 16 addresses and the classifier drew no real university, so a
keyserver source scoped to higher education is not refuted by this run. It is
also not proposed, and deliberately does not go on the roadmap: that would
promise work nobody has committed to, the reasoning ADR-0013 applied to
target-parameterised query URLs.

**`detect_entity_type`'s defect is left unfixed here.** It is real and it
corrupted this run's own breakdown, but fixing it changes which seeds
`seed_discoverer` produces for every scan, which is a behaviour change that
belongs in its own record rather than smuggled into a decline.

## Consequences
- v0.60's second planned feature does not ship, after the first did not
  either. The version's content is now two measurements, two declines and the
  work that replaced them.
- **theHarvester parity on this source is abandoned deliberately.**
  [PRD.md](../PRD.md) positions RadarCL as depth on one country rather than
  breadth of sources, and this is that position costing something: a source a
  competitor lists is declined because it does not pay off on Chilean targets.
- `scripts/pgp_keyserver_yield.py` and `scripts/data/pgp_cl.txt` stay in the
  tree. The harness is how the number reproduces, and re-running it is how
  anyone revisits this in a year when the SKS network has decayed further.
- **Any future prevalence claim in this repository needs a frame and a seed.**
  Three of the numbers ADR-0014, ADR-0017 and ADR-0018 rest on are convenience
  samples, two have now been re-measured and both moved. The third,
  ADR-0014's page-signal cascade, has not been.
- `detect_entity_type` is now known to be wrong on at least four inputs, and
  nothing downstream has been re-checked against that. Seed discovery picks its
  scoring table and its DuckDuckGo queries from it.
- No new dependency, no change to `app/`. The offline suite is untouched at
  153.

## Alternatives considered
- **Ship it anyway**, on the grounds that one request against
  `keyserver.ubuntu.com` never failed and would have found 16 addresses nobody
  had to crawl for. Rejected: it is precisely the override the pre-registration
  exists to prevent, and 0.08 against 0.65 is not a margin anyone could call
  close.
- **Scope it to higher education and re-measure** against a university-weighted
  frame, since INACAP gave 9 of 16 and the pilot's `uchile.cl` gave 206.
  Genuinely open, and rejected for now as cost: another full pre-registered
  cycle before any code exists, for a source whose corpus is decaying.
- **Lead the record on `keys.openpgp.org`'s policy**, arguing the source is
  obsolete rather than thin. True, and it would hold even had the yield passed.
  Rejected because it is not what the gate was written against, and a decision
  record should turn on the evidence that was actually pre-registered.
- **Combine this with the `detect_entity_type` defect in one record**, the way
  ADR-0017 combined six defects that shared one cause. Rejected because these
  two do not share a cause; the classifier bug would exist had the yield been
  excellent.
- **Fix the pilot and re-run it** rather than declining outright, by picking
  eight *unrecognisable* targets. Rejected as incoherent: a pilot chosen to
  avoid the researcher's recognition is a random sample, and that is the run
  that was already done.
