# Does a PGP keyserver recover `.cl` addresses worth the request?

Research notes for [ROADMAP.md](../../ROADMAP.md)'s v0.60 item 2, a PGP
keyserver source in `seed_discoverer.py`.

**This half of the file is a pre-registration**, written and committed before
the sampled run. The roadmap item itself asks for exactly this: *"Measure
recovered addresses per page spent before building the PGP source."* It says
so because of
[ADR-0013](../adr/0013-curated-source-stage-removed-after-measurement.md),
where a source that sounded obvious shipped, measured at zero, and was
deleted.

The sibling `.cl` hint in the same version was measured the same way and
[declined](../adr/0019-the-sibling-cl-hint-is-measured-and-declined.md). This
one is expected to go the other way, which is exactly when a threshold
committed in advance is worth the most.

Dated 2026-07-25.

## What already works, checked live rather than assumed

Four keyservers were queried on 2026-07-25 for `@uchile.cl`:

| Keyserver | Domain search |
|---|---|
| `keyserver.ubuntu.com` | **200**, returns results |
| `pgp.mit.edu` | **200**, returns results |
| `keys.openpgp.org` | **400 Invalid request** |
| `keys.mailvelope.com` | **400 Invalid search parameter** |

`keys.openpgp.org` is not broken, it is policy. Its
[API documentation](https://keys.openpgp.org/about/api) states that lookup by
email address takes *"only exact matches"* and *"requires opt-in by the owner
of the email address"*, and that all requests return one key or none. It was
built after the 2019 certificate-poisoning attacks specifically so the key
corpus cannot be enumerated. **The modern, maintained keyserver deliberately
forecloses this source; the two that answer are the legacy SKS-era network.**

That matters for what the addresses mean, below.

## The pilot, and why it is only a pilot

Eight domains, the same target list ADR-0013 used, so a convenience sample
reported as nothing more:

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

253 addresses from 8 MIT requests is roughly 32 per request, against the
crawler's best measured yield of 0.65 addresses per page
([ADR-0014](../adr/0014-country-is-never-inferred-from-a-com-address.md)'s
`nunoa.cl` control). Dropping `uchile.cl` as an outlier still leaves ~6.7.

Yield is plainly not the problem. Two other things are, and neither is
measured yet.

**Staleness.** These are SKS-era keys, some uploaded in the 1990s. The
`uchile.cl` results are heavy with `dcc.uchile.cl` and `ing.uchile.cl`
academic addresses of exactly that vintage. A source returning 206 dead
addresses is worse than one returning nothing: it inflates the result count
with bounces, which is the failure
[ADR-0016](../adr/0016-catch-all-domains-are-not-valid.md) exists to prevent.

**Provenance.** Anyone can upload a key bearing any UID. A keyserver address
is an unverified claim by whoever uploaded it, not an assertion by the domain.
This is the same shape as the sibling-`.cl` ownership problem ADR-0019 dealt
with, and it is why the measurement gates on verification rather than on
presence.

## Frame and sample

**Frame:** the 1597 registrable `.cl` domains belonging to Wikidata
organisations with `P17` (country) = `Q298` (Chile) — the same pool the
catch-all re-measurement drew from, constructed in
[sibling-cl-prevalence.md](sibling-cl-prevalence.md) with its biases recorded
there. Wikidata's notability skew applies here too, and this time it cuts
toward the result: universities are over-represented in Wikidata relative to
the Chilean domain population, and universities are exactly where PGP keys
live.

**Draw:** n = 100, `random.Random(20260726).sample(sorted(pool), 100)`, in
`scripts/data/pgp_cl.txt`. Independent of the catch-all draw over the same
pool; overlap is possible and harmless, the questions are unrelated.

**Verification subsample:** 60 recovered addresses drawn at random from
everything the keyservers return, verified through the existing
`app/core/verifier.verify()` with MX and SMTP. Sixty rather than all of them
because the catch-all run measured 35% of Chilean mail servers hanging up on
an unfamiliar probe, and opening hundreds of SMTP conversations to establish
a rate is not proportionate.

## Pre-registered decision rule

**Ship the source if it recovers at least 0.65 live addresses per keyserver
request.**

"Live" means the address is not `INVALID` after verification. UNKNOWN counts
as live, per
[ADR-0009](../adr/0009-mx-resolution-failure-is-unknown.md): a server that
would not answer is not evidence the mailbox is dead, and treating it as such
is the mistake that ADR corrected.

0.65 is not invented for this measurement. It is the crawler's own best
measured yield per page, from ADR-0014's `nunoa.cl` control, the most
favourable number the existing pipeline has produced. A new source that
cannot beat the best page RadarCL already crawls is not worth a request.

The estimate is `(recovered addresses x live share) / requests made`, with the
live share taken from the 60-address subsample and its 95% Wilson interval
carried into the final figure, so the gate is judged against the interval
rather than a point estimate — the same discipline the sibling run used.

## Also to be reported

- **Yield by entity type**, using `seed_discoverer.detect_entity_type`. The
  pilot suggests universities dominate; if the source only works for
  universities, that is a finding about scope rather than a failure.
- **Both keyservers separately.** `pgp.mit.edu` is long deprecated and
  intermittently unavailable, so a result that depends entirely on it is a
  result with a single point of failure worth naming.
- **Non-response**, as ever: requests that time out or error, counted apart
  from domains that genuinely have no keys.
- **Duplication is out of scope and stated as such.** Whether these addresses
  are ones the crawler would have found anyway needs a crawl per domain, which
  is the 451-page shape of ADR-0013's measurement. Not run. The gate is
  therefore "worth the request", not "adds something the pipeline lacks", and
  the ADR must not claim the stronger thing.

---

*Everything above was committed in `6e7326c` before the run. Below is the run.*

# Results, 2026-07-25

## The pilot overstated the source by roughly 400 times

| | Pilot, 8 recognisable targets | Random draw, n=100 |
|---|---|---|
| Addresses per request | ~32 | **0.08** |
| Domains with any keys | 6 of 8 | **7 of 100** |
| Distinct addresses | 253 | **16** |

200 requests, 189 answered, 11 non-response. **Live yield 0.08 per request,
interval [0.06, 0.08], against a gate of 0.65. Missed by about eight times.**

Every address recovered from a hundred Chilean organisations:

| Domain | Addresses |
|---|---|
| `inacap.cl` | 9 |
| `minera.cl` | 2 |
| `bcn.cl`, `contraloria.cl`, `senado.cl`, `uda.cl`, `municipalidadillapel.cl` | 1 each |

The gap between the two columns is the entire lesson. The pilot used
ADR-0013's target list, which contains two universities out of eight, and
universities are where PGP keys live. Picking recognisable targets overstated
a source by two and a half orders of magnitude, in the same session that
declined the sibling hint for the same class of error.

## Liveness is weak evidence, and it does not matter

60 were to be verified; only 16 existed, so all 16 were.

| Status | Count |
|---|---|
| VALID | 0 |
| CATCH_ALL | 0 |
| UNKNOWN | 15 |
| INVALID | 1 |

15 of 16 = 93.8%, [71.7%, 98.9%]. Counted as live per
[ADR-0009](../adr/0009-mx-resolution-failure-is-unknown.md), and the phrase
that fits is **not disproved** rather than confirmed: no address was
positively verified. The same servers that hung up on 35% of the catch-all
run hung up here.

It changes nothing. At 100% live the yield is still 0.08.

## `pgp.mit.edu` is as unreliable as its reputation

| Keyserver | Addresses | Failed requests |
|---|---|---|
| `keyserver.ubuntu.com` | 12 | 0 of 100 |
| `pgp.mit.edu` | 14 | **11 of 100** (7 × HTTP 408, 4 × protocol error) |

A source resting on MIT would carry an 11% failure rate. Ubuntu's server was
flawless and cheaper, and on its own recovers 12 of the 16.

## The entity breakdown is unreliable, and that is a finding

| Detected type | Domains | With keys | Addresses |
|---|---|---|---|
| company | 67 | 3 | 12 |
| government | 4 | 3 | 3 |
| municipality | 25 | 1 | 1 |
| university | 4 | 0 | 0 |

**`detect_entity_type` mislabelled every domain in the university bucket.**
The four were `editorialusach.cl` (a publisher), `huachipatofc.cl` (a football
club), `mguc.cl` and `supereduc.cl` (the schools regulator). Substring
matching on `usach`, `uc` and `educ` does that.

Two consequences, and the second matters more:

- The breakdown above cannot be read as "universities have no keys".
- **No real university was drawn**, so this run does not test the case the
  pilot was strongest on. INACAP, the one higher-education institution in the
  sample, produced 9 of the 16 addresses, which is consistent with the pilot's
  `uchile.cl` result without confirming it.

The gate is population-wide, so this does not rescue the source: universities
are rare among the organisations a user targets, and a source that pays off
only there has to be measured there before it can claim so.

## Limits

- **Duplication was never measured**, as the pre-registration said it would
  not be. Whether these 16 addresses are ones the crawler would find anyway is
  unknown. Since the source fails on yield alone, the question is moot; had it
  passed, it would have been the next thing to run.
- **One date, one network**, and the SKS network's contents change slowly but
  its availability does not.
- **The classifier defect is not fixed here.** It is recorded and left, since
  fixing it changes seed discovery's behaviour and belongs in its own change.
