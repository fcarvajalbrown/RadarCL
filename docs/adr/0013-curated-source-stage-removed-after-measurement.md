# 0013 - The curated-source stage is removed after measuring it

## Status
Accepted. Supersedes [0012](0012-curated-sources-assert-identity.md).

## Date
2026-07-24

## Deciders
Felipe Carvajal Brown

## Context
[ADR-0011](0011-ct-fallback-and-source-hygiene.md) replaced a curated list
of Chilean institutional sites after five of eight entries had rotted, and
[ADR-0012](0012-curated-sources-assert-identity.md) added a guard so a
source that keeps answering 200 while becoming something else fails a test.
Both ADRs improved how the list was maintained. Neither asked what it
returned, and [PRD.md](../PRD.md) rests a competitive claim on it: that
Chile-specific source curation, not source volume, is what RadarCL has that
Subfinder and theHarvester do not.

`_semantic_seeds_from_url` recognised a curated source by `base_host not in
domain` and then kept only links satisfying `domain in full.lower()` - the
target's domain appearing somewhere in the link URL. Checked live on
2026-07-24 against thirteen source-target pairs, every curated homepage
answered 200 and not one carried a single anchor naming the target:

| Source | anchors | anchors naming the target |
|---|---|---|
| ccs.cl | 341 | 0 |
| chilecompra.cl | 200 | 0 |
| anid.cl | 190 | 0 |
| cmfchile.cl | 164 | 0 |
| mifuturo.cl | 141 | 0 |
| consejoderectores.cl | 119 | 0 |
| subdere.gov.cl | 109 | 0 |
| sinim.gov.cl | 87 | 0 |
| sofofa.cl | 72 | 0 |
| leylobby.gob.cl | 34 | 0 |
| portaltransparencia.cl | 23 | 0 |
| bcn.cl | 0 | 0 |

An institutional homepage does not link to a target municipality, ministry
or firm by URL, so `_score_link` was never reached and the stage's entire
contribution was twelve homepage seeds.

Two measurements then asked whether those seeds pay off anyway. Targets
were two per entity type: `nunoa.cl`, `providencia.cl`, `minsal.cl`,
`senado.cl`, `uchile.cl`, `usach.cl`, `codelco.cl`, `entel.cl`.

**Each source crawled alone**, 50 pages, depth 3, no target filter, so
every address found was counted:

| Result | Value |
|---|---|
| Pages fetched | 451 of 600 budgeted |
| Distinct `.cl` addresses harvested | 97 |
| Addresses belonging to any of the eight targets | **0** |

The 97 are the sources' own switchboards and staff - 32 `@subdere.gov.cl`,
12 `@consejoderectores.cl`, 10 `@sofofa.cl` - plus third parties with no
relation to anything, since `ccs.cl` yielded `admin@epictravels.cl` and
`carla@brandora.cl`. All 97 are discarded by the target filter in
`pipeline.crawl_and_extract`. Deep-crawling the curated sources is
therefore not an untested alternative; this is that test, and it returns
the sources' own contacts.

`portaltransparencia.cl` and `anid.cl` fetched **zero** pages. Both answer
403 to `crawler.py`'s `RadarCL/0.1` token. ADR-0011 found that 403 and
fixed it in `seed_discoverer` alone, leaving the stage seeding two URLs the
crawler consuming them could not open. `bcn.cl` fetched one page and, at 48
characters of visible text and no anchors, could never have contributed.

**The full pipeline, with and without the stage**, stages 1-3 held
identical by replaying the captured Certificate Transparency result, both
arms at 60 pages:

| Target | seeds from stages 1-3 | curated seeds kept | curated share of budget | with | without |
|---|---|---|---|---|---|
| nunoa.cl | 20 | 0 | 2% | 24 | 24 |
| providencia.cl | 20 | 0 | 2% | 26 | 26 |
| minsal.cl | 20 | 0 | 0% | 1 | 1 |
| senado.cl | 20 | 0 | 0% | 2 | 2 |
| uchile.cl | 20 | 0 | 0% | 14 | 14 |
| usach.cl | 20 | 0 | 0% | 9 | 9 |
| codelco.cl | 20 | 0 | 0% | 1 | 1 |
| entel.cl | 12 | 4 | **60%** | 0 | 0 |

On seven of eight targets the stage contributed nothing at all, not even
its twelve homepage seeds: stages 1-3 fill `max_seeds=20` before it
appends, so truncation discards everything it adds. On `entel.cl`, the one
target where stages 1-3 came up short, its four company sources did get in
and took 36 of 60 pages for no addresses. The stage fires precisely when it
is most expensive.

It also spent 3 to 4 HTTP fetches and between 1.0s and 6.8s of discovery
time on every single scan, discarded in all eight cases.

## Decision
**The curated-source stage is removed**, along with `_KNOWN_SOURCES` and
the identity-phrase guard ADR-0012 introduced. Every mechanism that was
measured returned zero addresses for the target, and the one case where the
stage reached the crawler cost 60% of a scan's budget. A stage that cannot
be shown to contribute is removed rather than maintained.

This supersedes ADR-0012 outright: that ADR's entire subject is a guard
over `_KNOWN_SOURCES`, and the data structure is gone. It **narrows**
ADR-0011 rather than superseding it, following the precedent ADR-0012 set
in its own Decision. ADR-0011's curated-source table and live test are
void; its crt.sh to Cert Spotter chain, its 20s and 10s timeouts, its
rejection of MerkleMap and its browser User-Agent for `seed_discoverer` all
still govern shipping code and need an Accepted ADR standing behind them.

**DuckDuckGo becomes stage 4** and the pipeline is four stages. Entity
detection stays: the scoring tables and the DuckDuckGo query templates both
read it, so `detect_entity_type` and `_CL_MUNICIPALITIES` are untouched.

**The link filter keeps only links whose host carries the domain.** With
the curated branch gone, `_semantic_seeds_from_url` has one kind of caller,
so the `base_host not in domain` test and the loose `domain in full.lower()`
match go with it. That loose match was wrong on its own terms as well as
dead: it counted an off-site link carrying `?ref=nunoa.cl` as internal. An
offline test now covers it.

**`crawler.py` sends the browser User-Agent**, and `USER_AGENT` is defined
there as one constant that `seed_discoverer` imports. ADR-0011 decided
deliberately that `crawler.py` would keep its own token, so this reverses a
recorded decision rather than tidying an oversight. The reason is that
`portaltransparencia.cl` and `anid.cl` answer 403 to the old token and 200
to this one, and that applies to any crawl reaching those hosts, not only
to seeds this ADR is deleting. `crawler.py` holds the constant because it
is the lower-level of the two modules; one constant rather than two is what
keeps them from drifting.

The honest bot token ADR-0011 measured, `Mozilla/5.0 (compatible;
RadarCL/0.4.0; +<repository URL>)`, returns 200 on both sites and names the
tool. It was weighed again here and not taken, so that the tool sends one
string everywhere rather than two that differ for no reason a reader could
infer.

**Version 0.4.0 absorbs this** rather than becoming 0.4.1. No `v0.4.0` tag
and no Release exist, so 0.4.0 has never left the build machine, and
shipping a 0.4.0 that advertises curated sources followed by a 0.4.1
removing them would invent a history that did not happen.

## Consequences
- PRD.md's competitive claim loses its implementation. Chile-specific
  curation is still what would differentiate RadarCL from Subfinder and
  theHarvester; there is now nothing in the code making it true, and the
  PRD says so rather than continuing to claim it.
- Seed discovery makes 3 to 4 fewer HTTP requests per scan and returns
  between 1.0s and 6.8s sooner, depending on entity type.
- A scan whose stages 1-3 yield fewer than 20 seeds now crawls fewer,
  better seeds instead of filling the gap with institutional homepages.
  `entel.cl` went from spending 60% of its budget on four such sites to
  spending none, with identical results.
- Any crawl reaching `portaltransparencia.cl` or `anid.cl` by ordinary link
  following now gets 200 instead of 403, which is a change in the
  crawler's reach that has nothing to do with seed discovery.
- Sites that block browser-string traffic, or that treat it as consent to
  serve a heavier page, now see the crawler differently. Nothing in the
  measurement suggested this, and it is recorded because reversing
  ADR-0011's split is the kind of change whose effects show up somewhere
  other than where it was made.
- The offline suite drops the five curated-list tests and gains two link
  scoring tests: 107 to 104. The live suite loses the identity check.
- `_KNOWN_SOURCES`, `_semantic_seeds_from_url`'s dual-caller branch and the
  identity-phrase machinery are gone, about 268 lines against 93 added.
- The one mechanism never measured is seeding a per-source query URL built
  from the target rather than its homepage - `leylobby.gob.cl`'s search for
  a named institution, `portaltransparencia`'s per-organism page. It is
  recorded under Alternatives below and nowhere else: it is not a planned
  item, and putting it on the roadmap would promise work nobody has
  committed to. Two of the twelve sources would need the User-Agent change
  above before it could be tried at all.
- No new dependency. `vendor/`, `SHA256SUMS.txt` and
  `requirements-core.lock` are untouched.

## Alternatives considered
- **Probe target-parameterised query URLs before deciding**: measure
  whether seeding each source's search or per-organism URL, built from the
  target, returns target addresses, and only remove if that fails too.
  Rejected as the decision for now, and kept as a roadmap item: it would
  hold a stage measured at zero in shipping code while a replacement
  mechanism is investigated, and every source would need a hand-built URL
  template that rots exactly the way ADR-0011 documented.
- **Keep the homepage seeds and delete only the unreachable branch**: the
  smallest diff, and it would leave ADR-0012's guard standing. Rejected
  because truncation already discards the seeds on seven of eight targets,
  so it preserves a stage whose only measurable effect is the `entel.cl`
  case, which is the harmful one.
- **Repair the filter so the scoring tables fire on curated sources**:
  score their links by keyword and crawl the directory pages that surface.
  Rejected on the measurement rather than on principle - crawling those
  sites to depth 3 is exactly what the 451-page run did, and it returns
  their own addresses, all of which the target filter discards.
- **Narrow the list to the sources that pay off**: the ordinary response to
  a list with weak entries. Rejected because none of the twelve pays off;
  narrowing to the subset that works leaves the empty set.
- **Gate the stage so it only runs when stages 1-3 come up short**: spend
  the budget only when there is budget spare. Rejected because `entel.cl`
  is that case, and it is the one where the stage cost 60% of the crawl for
  nothing. The gate would fire the stage exactly when it is most expensive.
- **Leave `crawler.py`'s User-Agent alone**: ADR-0011 decided it
  deliberately, and with the curated seeds gone the two 403 sources stop
  being seeded anyway. Rejected because the crawler still reaches those
  hosts by following links, where a 403 reads as an unreachable host rather
  than as a token being refused.
