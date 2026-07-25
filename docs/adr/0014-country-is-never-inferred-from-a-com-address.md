# 0014 - Country is never inferred from a `.com` address

## Status
Accepted. Narrows [0003](0003-crawl-phase1-phase2-scope.md).

## Date
2026-07-24

## Deciders
Felipe Carvajal Brown

## Context
[ROADMAP.md](../../ROADMAP.md) phrased v0.50 as adding `.com` alongside `.cl`,
a filter change. [docs/research/dotcom-attribution.md](../research/dotcom-attribution.md)
argued on 2026-07-24 that the framing was wrong, and ranked six page-level
signals that might replace the TLD as the unit of attribution. Measuring those
signals showed the framing is wrong *and* that the ranking is backwards.

Three findings decide this ADR.

**The `.cl` filter never covered the whole pipeline.** `crawl_and_extract`
applies it to scraped addresses only, through `extractor._EMAIL_RE`. The
pattern-generated branch has no filter at all. Reproduced offline with a stub
crawler, `target_domain="bhp.com"` and pattern `{first}.{last}`:

```
jimmy.nunez@bhp.com
sarah.wilson@bhp.com
site.manager@bhp.com
```

`sarah.wilson@bhp.com` is the failure the research notes describe - a foreign
colleague's address in a file labelled Chilean contacts - and it has been
reachable since pattern generation shipped. [PRD.md](../PRD.md) calls the
`.cl` filter a permanent scope boundary. The code has never enforced it.

**The research file's ranked signals do not survive measurement.** Sixteen
reachable homepages and contact pages, seven Chilean-owned `.com` against nine
foreign `.com`. A third of large corporates refused the crawler outright: eight
of twenty-four homepages answered 403 or timed out, `bhp.com` among them, so the
flagship case is unreachable before any attribution logic applies.

The ground truth in the first two tables below is **corporate ownership**,
because that is the question the roadmap item asked. It is the wrong question,
and the tables are kept in those terms only to show why. What a page signal can
actually assert is that **the page carries Chilean evidence**, which is a
different claim and the one this ADR settles on; the difference is worked out
after the tables.

| Signal | Chilean | Foreign | False negative | False positive |
|---|---|---|---|---|
| Valid RUT | 0/7 | 0/9 | 100% | 0% |
| `lang="es-CL"` | 1/7 | 0/9 | 86% | 0% |
| `+56` phone | 1/7 | 0/9 | 86% | 0% |
| Country path segment | 1/7 | 0/9 | 86% | 0% |
| Chilean place words | 7/7 | 4/9 | 0% | **44%** |
| Sibling `.cl` resolves | 5/7 | 5/9 | 29% | **56%** |

The RUT is the file's first-ranked signal, described as the one worth building
on. It appeared on **0 of 200 crawled pages** - Chilean `.com`, foreign `.com`
and a `nunoa.cl` control alike, including ten municipal pages that did carry
addresses. The detector was self-tested before that number was trusted: it
accepts valid modulo-11 check digits, rejects wrong ones, and ignores bare
eight-digit numbers and phone-shaped strings.

The sibling-`.cl` signal is worse than a coin flip rather than merely weak.
Foreign firms hold `riotinto.cl`, `angloamerican.cl`, `teck.cl`, `glencore.cl`
and `nestle.cl`; Chilean-owned `sqm.cl`, `cencosud.cl` and `latamairlines.cl`
do not resolve.

Six further signals were tested that the research file does not list. All
failed, several instructively:

| Signal | Chilean | Foreign | Note |
|---|---|---|---|
| `hreflang="es-CL"` | 0/7 | **1/9** | fires only on `albemarle.com`, a US company |
| JSON-LD `addressCountry` | 0/16 | 0/16 | no corporate homepage publishes it |
| Comuna gazetteer | 1/7 | **2/9** | `teck.com` names Iquique and Las Condes |
| `SpA` legal form | 0/7 | 0/9 | large firms are S.A.; SpA is a smaller-company form |
| Chilean institutional lexicon | 2/7 | 0/9 | `casilla`, `comuna`, `clp` |
| National-format CL phone | 2/7 | 1/9 | catches numbers written without `+56` |

The pattern is consistent across all twelve: every signal with precision has
recall of 29% or less, and every signal with recall has false positives.

What does work is the **union of the surviving signals**, evaluated as a cascade
rather than summed as a score. Measured with the implementation this ADR ships,
it fires on **4 of 7 Chilean-owned `.com` and 1 of 9 foreign-owned**.

That single foreign hit is what forced the question of what the cascade is
actually claiming, and it is worth stating plainly rather than filing as an
error rate. `teck.com/about/contact` says:

> Teck Resources Chile, Alonso de Córdova 4580, Piso 10, Las Condes,
> Santiago, Chile - t: 56 2 2 4645700

The page carries a Santiago address and a real Chilean landline. Teck is
Canadian, so under ownership as ground truth this is a false positive; under
page evidence as ground truth it is correct, and the signal is doing exactly its
job. **This ADR adopts page evidence**, because it is the only claim the code
can support and because inferring ownership from a page is the thing being
rejected here. On that reading the cascade makes no errors in the sample: 4/7
and 1/9, all of them right.

It also cuts the other way, and this is why the recall-bearing signals stay out.
`angloamerican.com`, `albemarle.com` and `glencore.com` each score a Chilean
place word from a passing mention of Chile in a list of global operations. A
passing mention is not evidence the page is Chilean, and place-word counting
cannot tell it apart from Teck's actual office - which is the precision problem
restated, not dissolved by the change of ground truth.

One implementation finding belongs here because it shaped the code.
`phonenumbers` accepts the US ZIP+4 `99201-0301`, printed on that same Teck
page, as the valid Chilean mobile `+56 9 9201 0301`; nine digits beginning with
9 are indistinguishable from a Chilean mobile. Leniency does not fix it -
`STRICT_GROUPING` keeps the ZIP and discards real numbers written `22 818 5000`
- so `provenance._has_cl_phone` rejects ZIP+4-shaped matches explicitly. A
hand-rolled `+56` regex never saw this because it never matched national formats
at all, which is a fair warning about what a weaker implementation hides rather
than an argument for one.

**Attribution was never the binding constraint.** Forty pages crawled per
target, counting every address of any TLD:

| Target | Addresses per page | What was found |
|---|---|---|
| `codelco.com` | 0.05 | 2 addresses, both `.cl` |
| `falabella.com` | 0.00 | nothing |
| `sonda.com` | 0.00 | nothing |
| `teck.com` (foreign) | 0.45 | 18, of which 13 `@teck.com` |
| `nunoa.cl` (control) | 0.65 | 26, of which 23 `@nunoa.cl` |

Widening the filter to `.com` would have added nothing on all three Chilean
targets. `codelco.com`'s only two addresses were `@codelco.cl` and
`@acuerdocodelcosqm.cl`, which the current filter already collects. The one
target where a `.com` filter pays off is the Canadian one. This is the same
shape as [ADR-0013](0013-curated-source-stage-removed-after-measurement.md):
an intuitive addition that measurement shows contributes nothing to the target.

The external lookups the research file listed as unverified were queried:

- **Mercado Publico** is real. `BuscarProveedor` answers `203 Ticket no valido`
  without a ticket and accepts ChileCompra's published demo ticket, and
  rate-limits at `429` on a second call. It is keyed by RUT.
- **SII** exposes no queryable documented API. `zeus.sii.cl/cvc_cgi/stc/getstc`
  responds but expects POST and is captcha-gated; the consultation page is a
  JavaScript portal. Also keyed by RUT.
- **IP geolocation** locates a CDN, as suspected: `codelco.com` serves from
  CLOUDFLARENET, `sqm.com` from MSFT, `riotinto.com` from THALES-IMPERVA, and
  RDAP returns no country for any of them.

Both registries take a RUT as input, and the RUT is the signal that measured
zero. They cannot be reached from what a page provides.

One correction to RadarCL's existing assumption is worth recording, since it
cuts against the tool rather than for it. NIC Chile's regulation, Article 7,
reads: "Any natural or legal person, whether domestic or foreign, may hold .CL
domain names." The `.cl`-implies-Chile inference the tool already makes is a
strong practical convention, not a guarantee.

## Decision
**RadarCL never infers a country from an email address.** The `.cl` suffix is
treated as what it is - a convention strong enough to scope a tool around, and
not evidence about any individual mailbox.

**The scraped-address filter stays `.cl`-only**, unchanged, in
`extractor._EMAIL_RE`.

**A non-`.cl` address is emitted only when the user names that domain**, through
an explicit target domain, and it carries no Chilean claim of any kind. This
legitimises what the generated branch already did, under the user's own
instruction rather than silently.

**The cascade ships as a flag, never as a filter.** A new Qt-free
`app/core/provenance.py` exposes `chile_evidence(html, url)`, returning the
names of the signals that fired on the page an address was found on. It is
attached to `Discovery`, computed once per page rather than once per address,
and it annotates results. It does not decide what is collected. At 57% recall a
filter would silently discard real addresses on 43% of Chilean-owned sites,
which is the failure mode
[ADR-0009](0009-mx-resolution-failure-is-unknown.md) documented for treating an
absence of evidence as evidence of absence.

The cascade admits `lang-es-cl`, `rut`, `phone-cl`, `lexicon` and `path-cl`:
the signals that assert something about the page rather than about the country
being mentioned on it. Every signal excluded is excluded on a measurement, not
on taste: place-word counting and the comuna gazetteer because they cannot
separate a passing mention of Chile from an actual Chilean office, the sibling
`.cl` at 56% and because it is not a fact about the page at all, `hreflang`
because the only site declaring `es-CL` is American, JSON-LD `addressCountry`
because nobody publishes it, and `SpA` because no firm in the sample uses it.

`rut` is admitted despite firing on 0 of 200 pages. It costs one regex over text
already parsed, it is the only signal here that is self-verifying rather than
circumstantial, and a signal that is silent is not a signal that is wrong. It
should be reviewed, not assumed, if a later sample still shows nothing.

**`python-stdnum` and `phonenumbers` are vendored** per
[ADR-0008](0008-vendored-core-dependencies.md) rather than hand-rolled.
`stdnum.cl.rut` is the canonical RUT validator, and `phonenumbers` carries
Google's real CL number-plan metadata, which is what lets `phone-cl` match
numbers written without `+56` - the difference between 1/7 and 2/7 recall in the
measurement above.

**Existing output contracts are untouched.** CSV keeps the shape
[ADR-0010](0010-export-contents-differ-by-format.md) gave it, VALID-only with
fixed columns, because evidence is run metadata and ADR-0010 already assigns run
metadata to JSON and HTML. The CLI's stdout stays three TSV fields, because
CLAUDE.md documents it as data-only so it pipes, and a fourth field breaks a
downstream `cut -f3` silently and at someone else's site.

**This narrows ADR-0003 rather than superseding it**, following the precedent
ADR-0013 set with ADR-0011. ADR-0003's two-phase crawl scope still governs
shipping code in full. Only its statement that the email filter always stays
`.cl`-only regardless of phase is qualified: it remains true of scraped
addresses and was never true of generated ones. ADR-0003's Status line is
unchanged.

## Consequences
- The roadmap item that motivated v0.50 does not ship, and the version ships the
  measurement that closed it instead. "Add `.com`" was intuitive and, on these
  numbers, would have imported a Canadian miner's address book while adding
  nothing on Codelco, Falabella or Sonda.
- The pattern-generation path stops producing non-`.cl` addresses as a silent
  side effect and starts producing them as an answer to an explicit request.
  Anyone relying on the old behaviour without passing a target domain sees a
  change.
- `Discovery` gains a field. It is defaulted, so existing construction sites and
  `tests/test_pipeline.py` are unaffected.
- Two new vendored wheels, and `SHA256SUMS.txt` and `requirements-core.lock`
  regenerated. `phonenumbers` carries a large metadata payload for one country's
  number plan, which is a real cost accepted for the recall it buys.
- PRD.md's non-goal claimed a boundary the code did not enforce. It now
  describes what is true.
- The research file's ranking is corrected in place rather than left standing.
  Its "signal worth building on" section recommends the RUT, the one signal that
  never fired, and a reader arriving at it today would build the wrong thing.
- **The sample is small and the ADR does not pretend otherwise**: sixteen
  reachable domains and 200 crawled pages, on one date, from one network, and
  the foreign arm is nine domains. It is enough to reject the signals that
  failed outright and enough to justify a flag; it would not be enough to
  justify a filter, which is part of why the cascade is not one.
- A user reading `phone-cl` on a `teck.com` page is being told something true
  and something easy to over-read: the page has a Chilean number, not that the
  company is Chilean. The signal names are deliberately literal for that reason,
  and any UI or export surfacing them inherits the obligation not to relabel
  them as a nationality. The HTML report carries that caveat in Spanish, next to
  the column rather than in a footnote nobody reaches.
- **The desktop GUI collects evidence but does not display it.** It reaches the
  JSON and HTML exports the same way the CLI's does; the results table is
  unchanged. A column there would be the most likely place for a reader to
  compress "this page looked Chilean" into "this is a Chilean address", and the
  results table is in the part of the Qt layer ADR-0002 deliberately leaves
  untested, so the change with the worst failure mode would also be the least
  covered. It can be added later on evidence that users want it.
- `verify_all` accepts both two- and three-element tuples rather than taking a
  new required argument, because the `verify` subcommand reads bare addresses
  from a file and has no page behind them. That tolerance is deliberate, and it
  is why the `evidence` key is absent rather than empty for those records.
- Bot-hostility is now a documented limit rather than a surprise. A third of
  large corporate sites refuse the crawler, `bhp.com` among them, so the case
  that prompted this whole question cannot be reached at all.

## Alternatives considered
- **Add `.com` to the email filter**, the roadmap's original framing. Rejected
  on measurement: it adds nothing on the Chilean targets and pays off only on
  the foreign one, and it would put addresses carrying no country evidence into
  a file labelled Chilean contacts.
- **A provenance score as a confidence value**, the shape the research file
  proposed by analogy with ADR-0009's UNKNOWN. Rejected because summing these
  particular signals mixes two populations that do not blend: the precise ones
  contribute almost no recall and the recall-bearing ones are 44% and 56% wrong,
  so any threshold either admits `teck.com` or excludes most of Chile. The
  cascade keeps the precise signals and discards the rest rather than averaging
  them.
- **The cascade as a hard filter for `.com`**, automating the decision. Rejected
  because 43% of Chilean-owned sites fire nothing, so the tool would miss them
  silently, and because `teck.com` shows what the other direction costs: it
  fires correctly on page evidence, so a filter would have admitted a Canadian
  miner's address book on the strength of one Santiago office.
- **Close the boundary entirely**, filtering the generated branch to `.cl` and
  making PRD.md's non-goal literally true. The smallest diff, and defensible.
  Rejected because it deletes a capability that works, on the strength of a
  boundary the code never enforced, when the actual defect is silence rather
  than reach.
- **Look the organisation up in an external registry** - Mercado Publico, SII,
  or Wikidata's official-website property. Rejected for now because the two
  Chilean registries are keyed by RUT and the RUT measured 0/200, so the input
  is unavailable from a page. Wikidata was not measured: its query service
  refused the requests made here, and it is recorded as untested rather than
  rejected.
- **IP geolocation.** Rejected on measurement rather than on principle: all four
  hosts checked serve from Cloudflare, Microsoft or Imperva, and RDAP returns no
  country for any of them.
- **Hand-roll the RUT and phone checks** to avoid two vendored dependencies.
  Weighed and not taken; the modulo-11 check is trivial but the CL national
  number plan is not, and a regex approximating it measured worse than the
  library's metadata.
- **Widen the sample to 40-60 domains before deciding anything.** Rejected as a
  gate, because the signals that failed failed decisively and more domains would
  not revive a signal that scored 0/200. The sample limit is recorded above
  instead, and it is the reason the cascade ships as a flag.
