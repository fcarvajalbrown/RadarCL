# Attributing a `.com` address to Chile

Research notes for [ROADMAP.md](../../ROADMAP.md)'s v0.50 item, `.com`
domain support for Chilean companies with international domains. Nothing
here is decided. v0.50 revisits
[ADR-0003](../adr/0003-crawl-phase1-phase2-scope.md)'s `.cl`-only email
filter and needs its own ADR before any of this is implemented.

Dated 2026-07-24. Two kinds of claim appear below and they are labelled,
because the difference is what makes these notes worth keeping: what was
measured against live services here, and what was only read in a search
result and still needs checking.

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

## The signal worth building on

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
