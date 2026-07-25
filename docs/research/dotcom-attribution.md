# Attributing a `.com` address to Chile

Research notes for [ROADMAP.md](../../ROADMAP.md)'s v0.50 item, `.com`
domain support for Chilean companies with international domains.

**Decided, on the second half of this file.**
[ADR-0014](../adr/0014-country-is-never-inferred-from-a-com-address.md)
records the outcome and is the current statement; these notes are kept for
the measurements behind it. The first half was written before the signals
were tested and its ranking is wrong - jump to
[Measured against real pages](#measured-against-real-pages-2026-07-24) if
you are here to decide something.

Dated 2026-07-24 throughout, in two passes on the same day. Three kinds of
claim appear below and they are labelled, because the difference is what
makes these notes worth keeping: what was reasoned about, what was
measured against live services, and what was only read in a search result.
The order they appear in is the order they happened, so the reasoning that
turned out wrong is still here rather than quietly deleted.

## The question, and why it has no answer at the domain level

The roadmap item reads as a filter change - allow `.com` alongside `.cl`.
It is not. The `.cl` suffix is doing work no flag can replace: it is the
only reason RadarCL can claim a result is Chilean at all.

`jimmy.nunez@bhp.com`, at BHP's Escondida operation in the Atacama, and a
colleague in Melbourne share a registrar, a nameserver, an MX record and a
TLD. Nothing in DNS or registration data distinguishes them, because
nothing about the address encodes an office. Any formula promising to
decide country from a `.com` address is guessing, and being wrong here is
expensive in exactly the way this project cares about: it puts a foreign
stranger's address into a file labelled Chilean contacts.

The research literature reaches the same place from the other direction.
Work classifying sites by target country notes that prior approaches infer
country from the TLD, and that no country can be assigned to sites under
generic top-level domains, which the authors record as a bias in their own
dataset rather than a solved problem
([arXiv 2510.08101](https://arxiv.org/pdf/2510.08101)).

## Measured here, 2026-07-24

**Registration data carries no country.** RDAP was queried for three
`.com` domains through `rdap.org`. All three returned HTTP 200 with a
single `registrar` entity and no registrant address of any kind:

| Domain | Entities returned | Registrant country |
|---|---|---|
| `bhp.com` | registrar only | absent |
| `codelco.com` | registrar only | absent |
| `falabella.com` | registrar only | absent |

This matters because secondary sources say the opposite. At least one
states registrant country stays public post-GDPR on the grounds that it is
not personal data ([DN.org](https://dn.org/handling-redacted-fields-in-rdap-under-privacy-laws/)).
For these three domains it is simply not in the response. Do not build on
the field without re-checking it against the exact domains in scope.

**The sibling-ccTLD heuristic fails on the flagship case.** "A Chilean
company will also hold the `.cl`" is the obvious first idea:

| Sibling | Result |
|---|---|
| `bhp.cl` | does not resolve - `ConnectError` |
| `codelco.cl` | 200, redirects to `https://www.codelco.com/` |
| `falabella.cl` | 200, redirects to `https://www.falabella.com/falabella-cl` |

It works for two of three and fails for BHP, which is the case that
prompted the question. Useful as one signal among several; fatal as the
deciding one.

**Page-level signals do separate.** Four homepages, same fetch, counting
signals in the markup rather than reasoning about the domain:

| Page | `html lang` | `+56` phone | Chile words |
|---|---|---|---|
| `codelco.com` - Chilean firm on a `.com` | **es-CL** | 1 | 10 |
| `falabella.com/falabella-cl` | none | 0 | 2 |
| `riotinto.com` - foreign, has Chilean operations | en | 0 | 0 |
| `bbc.com` - control | en-GB | 0 | 0 |

Rio Tinto is the interesting row: it co-owns Escondida, so an
organisation-level test would call it Chilean. Its homepage does not, and
that is the correct answer for the page.

**`bhp.com` is bot-hostile.** Every request forcibly closed the connection
(`WinError 10054`) under the same browser User-Agent that works elsewhere.
The flagship case is unreachable before any attribution logic applies.

## Not verified here

Read in search results, plausible, unchecked. Verify before relying on any
of it.

- **Mercado Público API** - documented at
  [chilecompra.cl/api](https://www.chilecompra.cl/api/), reportedly free
  with a ticket issued by email, covering suppliers to over 1,000 state
  entities. Would answer "is this organisation a Chilean supplier" as a
  lookup rather than a heuristic. Not queried.
- **SII taxpayer lookup by RUT** - the official consultation page is
  [sii.cl/servicios_online/1039-1186.html](https://www.sii.cl/servicios_online/1039-1186.html).
  Third parties resell it as REST with free daily quotas; those are
  third-party intermediaries, not the SII, and their terms were not read.
- **IP geolocation** is quoted at roughly 95-99% accuracy at country level
  ([ipapi.is](https://ipapi.is/blog/ip-geolocation-accuracy.html)). Even
  taking that at face value it locates the server, which for any company
  of this size is a CDN edge. It answers a question nobody asked.
- **`.cl` registration implies nothing about nationality.** NIC Chile
  removed the local-contact requirement for foreign registrants in
  December 2013, so anyone worldwide may hold a `.cl`
  ([NIC Chile](https://nic.cl/normativa/reglamentacion-eng.html)). Worth
  confirming, since it also weakens the reverse inference RadarCL already
  makes about `.cl` addresses today.

## What looked strongest before measuring

**Superseded by the section below, and wrong.** The ranking here was reasoned
from what each signal would prove if present. Nobody had checked whether the
signals were present. When that was measured on the same day, the signal ranked
first appeared on none of 200 pages. Read
[Measured against real pages](#measured-against-real-pages-2026-07-24) before
acting on anything in this section; it is kept because the reasoning below is
still correct about what a RUT *means*, and wrong only about how often you get
to use it.

A RUT with a valid módulo-11 check digit is uniquely Chilean, and unlike
every other signal here it verifies offline: no API, no key, no network,
no new dependency. The algorithm is a weighted digit sum
([worked example](https://dev.to/fdograph/como-validar-un-rut-chileno-5335)),
and the check digit is what makes it strong - a random eight-digit number
formatted as a RUT fails, so it is an assertion rather than a pattern
match. That is the same shape as
[ADR-0012](../adr/0012-curated-sources-assert-identity.md)'s identity
phrases, pointed at pages instead of sources, and it survives the reason
0012 was superseded, since that was about a source list rather than about
asserting rather than assuming.

Ranked by what the measurements above support:

1. Valid RUT on the page - strongest, offline, self-verifying.
2. `html lang="es-CL"` - clean separation in the four-page test, one attribute read.
3. `+56` phone numbers in visible text.
4. Chilean place names and address forms.
5. A country segment in the URL path - `/falabella-cl`, `/es/chile`.
6. A sibling `.cl` resolving or redirecting to the `.com`.

Signals 5 and 6 are weak alone and are listed because they cost nothing
once a page is already fetched.

## Measured against real pages, 2026-07-24

Everything above this line was reasoned about. Everything below was run. Seven
reachable Chilean-owned `.com` against nine foreign-owned, plus a 200-page crawl
across `codelco.com`, `falabella.com`, `sonda.com`, `teck.com` and a `nunoa.cl`
control. Eight of twenty-four homepages answered 403 or timed out, `bhp.com`
among them, so a third of the target population refuses the crawler outright.

| Signal | Chilean | Foreign | False negative | False positive |
|---|---|---|---|---|
| Valid RUT | 0/7 | 0/9 | 100% | 0% |
| `lang="es-CL"` | 1/7 | 0/9 | 86% | 0% |
| `+56` phone | 1/7 | 0/9 | 86% | 0% |
| Country path segment | 1/7 | 0/9 | 86% | 0% |
| Chilean place words | 7/7 | 4/9 | 0% | 44% |
| Sibling `.cl` resolves | 5/7 | 5/9 | 29% | 56% |

The RUT is the signal the section above calls the one worth building on. It
appeared on **0 of 200 crawled pages** - Chilean `.com`, foreign `.com`, and ten
`nunoa.cl` municipal pages that did carry addresses. The detector was
self-tested first: it accepts valid check digits, rejects wrong ones, and
ignores bare eight-digit numbers and phone-shaped strings, so the zero is the
population's and not the code's.

The sibling-`.cl` idea is not merely weak, as this file guessed. It is worse
than a coin flip. Foreign firms hold `riotinto.cl`, `angloamerican.cl`,
`teck.cl`, `glencore.cl` and `nestle.cl`; Chilean-owned `sqm.cl`,
`cencosud.cl` and `latamairlines.cl` do not resolve.

Six signals this file never listed were tested too, and all failed:

| Signal | Chilean | Foreign | Note |
|---|---|---|---|
| `hreflang="es-CL"` | 0/7 | 1/9 | fires only on `albemarle.com`, a US company |
| JSON-LD `addressCountry` | 0/16 | 0/16 | no corporate homepage publishes it |
| Comuna gazetteer | 1/7 | 2/9 | `teck.com` names Iquique and Las Condes |
| `SpA` legal form | 0/7 | 0/9 | large firms are S.A. |
| Chilean institutional lexicon | 2/7 | 0/9 | `casilla`, `comuna`, `clp` |
| National-format CL phone | 2/7 | 1/9 | numbers written without `+56` |

**The unit of attribution is the page, not the company.** `teck.com` fires on a
Chilean phone because its contact page really does list a Santiago office. Teck
is Canadian and the signal is still right, because it reports what the page
showed. That distinction is what [ADR-0014](../adr/0014-country-is-never-inferred-from-a-com-address.md)
settles, and it is why place-word counting stays out: a passing mention of Chile
in a list of global operations is not the same as an office, and counting cannot
tell them apart.

**Attribution was never the binding constraint anyway.** Addresses per page
crawled, 40 pages each, counting every TLD:

| Target | Addresses/page | What was found |
|---|---|---|
| `codelco.com` | 0.05 | 2, both `.cl` |
| `falabella.com` | 0.00 | nothing |
| `sonda.com` | 0.00 | nothing |
| `teck.com` (foreign) | 0.45 | 18, of which 13 `@teck.com` |
| `nunoa.cl` (control) | 0.65 | 26, of which 23 `@nunoa.cl` |

### The unverified items, now queried

- **Mercado Público** is real: `BuscarProveedor` answers `203 Ticket no válido`
  without a ticket, accepts ChileCompra's published demo ticket, and rate-limits
  at `429`. It is keyed by RUT.
- **SII** exposes no queryable documented API. `zeus.sii.cl/cvc_cgi/stc/getstc`
  responds but expects POST and is captcha-gated. Also keyed by RUT.
- Both therefore need an input no page provides.
- **IP geolocation** locates a CDN, as this file suspected: `codelco.com` serves
  from CLOUDFLARENET, `sqm.com` from MSFT, `riotinto.com` from THALES-IMPERVA,
  and RDAP returns no country for any of them.
- **NIC Chile** confirmed, and it cuts against RadarCL rather than for it.
  Article 7: "Any natural or legal person, whether domestic or foreign, may hold
  .CL domain names." The `.cl`-implies-Chile inference the tool already makes is
  a convention, not a guarantee.
- **Wikidata** was not tested. Its query service refused both attempts. It is
  the one external route recorded as untested rather than rejected.

### Sample limits

Sixteen reachable domains, 200 crawled pages, one date, one network. The foreign
arm is nine domains. Enough to reject the signals that failed outright; not
enough to justify a filter, which is why the cascade ADR-0014 ships is a flag.

## What this changes about v0.50

Recorded as an open question, not a plan.

The roadmap phrases v0.50 as adding `.com` to a filter. The measurements
say the unit of attribution has to move: from the address, which carries
no country, to the page it was found on, which does. RadarCL already knows
that page - `Discovery.source_url` in `app/core/pipeline.py` carries it
today, and the crawler already has the markup in hand when the extractor
runs, so the signals above are available at the point of extraction
without a second fetch.

Two consequences worth weighing when that ADR is written. A provenance
score is a confidence, not a boolean, which is the same argument
[ADR-0009](../adr/0009-mx-resolution-failure-is-unknown.md) made for
UNKNOWN being a first-class verification outcome rather than a coin flip.
And multinationals increasingly encode country in the path rather than the
host, so `/falabella-cl` and `/es/chile` are ordinary internal links to
the current crawler with nothing marking them as country-scoped.
