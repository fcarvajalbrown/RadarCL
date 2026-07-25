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

*Results are appended below this line once the run completes. Nothing above it
is edited afterwards.*
