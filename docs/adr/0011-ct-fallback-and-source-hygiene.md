# 0011 - Certificate Transparency fallback and curated source hygiene

## Status
Accepted

## Date
2026-07-24

## Deciders
Felipe Carvajal Brown

## Context
`seed_discoverer.py` runs a five-stage cascade, and stages 1 and 4 are the
two that depend on somebody else's server still being there. Both were
checked live on 2026-07-24 rather than reasoned about, and both were worse
than the roadmap item assumed.

**Stage 1 had no fallback.** `_crtsh_subdomains` wrapped its single crt.sh
query in a bare `except Exception` and returned `[]`. crt.sh returned 502 for
roughly fifteen minutes during the investigation, which under the old code
meant the first and highest-yield stage of the cascade produced nothing and
said nothing.

Timings for `nunoa.cl`, measured:

| Source | Result |
|---|---|
| crt.sh, cold | 200 in 76.7s and 60.3s. 78 records, 13 unique hostnames |
| crt.sh, cached | 200 in 1.0s |
| crt.sh, during the outage | 502 in ~1.0s |
| Cert Spotter | 200 in 0.6s. 4 unique hostnames |

The old timeout was 30s, which is longer than a cached crt.sh query and far
shorter than a cold one. crt.sh was therefore already being truncated on any
domain nobody had queried recently, without that ever having been decided.

Cert Spotter's yield is lower because the free tier serves unexpired
certificates only; `expired=true` and `match_wildcards=true` were both tried
and changed nothing. It needs no API key. SSLMate publishes ten full-domain
queries an hour unauthenticated, and the eleventh returned
`429 rate_limited` with `Retry-After: 47`.

MerkleMap was the other named candidate and cannot be used at all:
`api.merklemap.com/v1/search` returns `401 Missing Authorization header`, and
its pricing is a single EUR 49 a month tier with no free API access.

**Stage 4's curated list was mostly wrong.** All eight hardcoded sources were
fetched. Five entries across four organisations had rotted:

| Entry | What it actually is |
|---|---|
| `transparencia.cl` (municipality and government) | A generic content blog. The state transparency portal is `portaltransparencia.cl` |
| `munitel.cl` (municipality) | A real-estate listings site |
| `cna.cl` (university) | The Centro Nacional de Arbitrajes. The accreditation commission is `cnachile.cl`, whose certificate chain does not validate under httpx |
| `fach.cl` (company) | The Chilean Air Force, and it does not respond |

Only `subdere.gov.cl`, `bcn.cl`, `mifuturo.cl` and `cmfchile.cl` were what
they claimed to be. This matters more than an ordinary stale constant:
[PRD.md](../PRD.md) names this curation, not source volume, as the thing
RadarCL has that Subfinder and theHarvester do not.

Separately, `portaltransparencia.cl` and `anid.cl` answer `403` to the
`RadarCL/0.1` User-Agent and `200` to a browser one.

## Decision
**A Certificate Transparency chain, not a single source.** `_ct_subdomains`
tries crt.sh, then Cert Spotter, and returns the first non-empty result. The
tuple of sources is built inside the function, as in
[ADR-0009](0009-mx-resolution-failure-is-unknown.md)'s `resolve_mx`, so each
source stays individually replaceable in tests.

A source that answers with no records has answered. The chain returns `[]`
in that case rather than raising, and raises `CTUnavailable` only when every
source errored. This is ADR-0009's distinction between a domain that does not
exist and a resolver that could not say, applied to CT data, and it is why a
`429` is classified as a failure: a refused question is not evidence of
absence.

`discover_seeds` catches `CTUnavailable` and continues. Stage 1 still fails
silently as a stage; the fallback lives inside it and does not become a
sixth stage.

**Timeouts of 20s for crt.sh and 10s for Cert Spotter.** This deliberately
shortens crt.sh rather than lengthening it. No budget short of two minutes
covers a cold crt.sh query, so 20s covers the cached case and hands
everything else to a source an order of magnitude faster. The consequence is
stated plainly below rather than hidden: on a cold domain, crt.sh's thirteen
names are traded for Cert Spotter's four.

**MerkleMap is not adopted.** Price, not capability.

**The curated lists are replaced, not extended.** Every entry below was
fetched and confirmed on 2026-07-24:

| Entity type | Sources |
|---|---|
| Municipality | `subdere.gov.cl`, `sinim.gov.cl`, `portaltransparencia.cl` |
| Government | `bcn.cl`, `portaltransparencia.cl`, `leylobby.gob.cl` |
| University | `mifuturo.cl`, `consejoderectores.cl`, `anid.cl` |
| Company | `cmfchile.cl`, `chilecompra.cl`, `sofofa.cl`, `ccs.cl` |

`leylobby.gob.cl` is the entry that carries the curation argument: the Ley
del Lobby obliges publication of *sujetos pasivos*, named public officials
with their institution, which is the closest thing Chile has to a public
directory of government staff. No generic international tool knows it exists.

`consejoderectores.cl` is used rather than `cruch.cl`, which does not
connect. `sii.cl`, `mercadopublico.cl`, `bolsadesantiago.com` and
`dipres.gob.cl` were tested and excluded: the first three serve a JavaScript
shell or a captcha rather than crawlable markup, and the last is a 266-byte
redirect stub.

**A live test guards the list.** `tests/test_seed_discoverer.py` refetches
every curated URL under the existing `smtp` marker, which in this project
means "needs a live internet connection". `pytest -m "not smtp"` stays fully
offline and CI is unaffected. Dated comments beside each entry record what
the organisation is; the test is what actually checks.

**The User-Agent becomes a browser string** in `seed_discoverer.py` only.
`_duckduckgo_seeds` was already sending exactly this string per-request, so
it moves to the client rather than being repeated. `crawler.py` keeps its
own.

## Consequences
- A crt.sh outage costs four hostnames instead of the entire stage. Verified:
  with the crt.sh leg forced to fail, `_ct_subdomains('nunoa.cl')` returned
  `nunoa.cl`, `www.nunoa.cl`, `serviciosenlinea.nunoa.cl` and
  `www.serviciosenlinea.nunoa.cl` from Cert Spotter.
- On a cold domain the chain now yields fewer hostnames than the old code
  would have on a good day, because 20s does not wait out a 60-second crt.sh
  query. In practice crt.sh serves recently-queried domains and Cert Spotter
  serves the rest. This is the accepted cost of failing over fast, not an
  oversight.
- Seed discovery makes outbound requests to `api.certspotter.com`, a second
  third-party disclosed the queried domain. The same privacy consideration
  ADR-0009 recorded for `dns.google` applies, and for the same reason: it
  only runs when the first source cannot answer.
- Heavy use can exhaust ten full-domain Cert Spotter queries an hour on a
  shared address. The 429 is silent, consistent with every other stage.
- Municipal and company scans stop spending crawl budget on a real-estate
  portal and an unreachable host.
- A scan of `bcn.cl` itself now draws the government sources. `bcn` was
  missing from the entity keyword table, so the Biblioteca del Congreso
  Nacional was classified as a company.
- The curated lists now need periodic attention, and the live test is what
  raises it. That test catches a source disappearing, not one quietly
  changing what it is, so a green run is weaker evidence than it looks:
  `munitel.cl` would have passed it while serving property listings.
- No new dependency. Both sources are `httpx` calls, so `vendor/`,
  `SHA256SUMS.txt` and `requirements-core.lock` are untouched.

## Alternatives considered
- **MerkleMap behind an optional `RADARCL_MERKLEMAP_TOKEN`**: honest about
  the paid gate and costs nothing when unset. Rejected because it ships a
  code path neither maintainer nor contributor can exercise without paying
  EUR 49 a month, which is an untested branch pretending to be a feature.
- **`rapiddns.io` as a third keyless source**: measured 8 hostnames for
  `nunoa.cl`, five of which crt.sh did not have, so it would genuinely add
  coverage. Rejected because it is HTML scraping with no API contract and
  breaks whenever the page markup changes. Reconsider if two CT sources prove
  insufficient in practice.
- **Query every source and merge the results**: best possible coverage.
  Rejected because it doubles the requests on every session and spends the
  ten-an-hour Cert Spotter allowance even when crt.sh answered fine.
- **Any HTTP 200 stops the chain, including an empty body**: a stricter
  reading of ADR-0009's short-circuit. Rejected because CT has no definitive
  negative. "No certificates logged" and "this source holds no data for you"
  are indistinguishable from the outside, unlike NXDOMAIN.
- **Raise the crt.sh timeout to 90s instead**: preserves the higher yield,
  thirteen names rather than four. Rejected because it puts a minute and a
  half of blank progress bar in front of the user before seed discovery has
  produced anything.
- **An honest bot User-Agent**, `Mozilla/5.0 (compatible; RadarCL/0.4.0;
  +<repository URL>)`: tested and returns 200 on both sites that reject the
  current token, byte-identical to the browser string, while still naming the
  tool. This was the recommendation. Rejected in favour of the plain browser
  string.
- **Keep the four rotted sources and add alongside**: non-destructive.
  Rejected because sending a crawler at a real-estate portal is worse than
  sending it nowhere, and the PRD's claim does not survive a list that is
  mostly wrong.
- **`scripts/check_sources.py` instead of a marked test**: more visible and
  more reportable. Rejected because nothing runs a script unprompted, which
  is precisely how `munitel.cl` survived.
