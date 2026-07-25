# 0022 - A parser is not a source, and does not need a gate

## Status
Accepted

## Date
2026-07-25

## Deciders
Felipe Carvajal Brown

## Context
Cloudflare's Scrape Shield rewrites published addresses two ways: a `mailto:`
anchor becomes a link to `/cdn-cgi/l/email-protection#<hex>`, and an inline
address becomes `<span class="__cf_email__" data-cfemail="<hex>">`. The payload
is a single-byte XOR whose key is the first octet of the ciphertext, so the key
travels with the message.

Cloudflare does not present this as encryption. The published analyses put it
plainly: storing the key beside the ciphertext is barely better than sending
the address in clear, and the stated purpose is to be *"enough to throw off the
basic scripts that hunt for `mailto:` links"*. `extract_emails` was exactly such
a script, and it already de-obfuscated the `user [at] domain.cl` convention -
the same job against a form that was common a decade earlier.

Measured before building, 100 registrable `.cl` domains drawn with
`random.Random(20260727)` from the frame documented in
[sibling-cl-prevalence.md](../research/sibling-cl-prevalence.md), one homepage
GET each:

| | |
|---|---|
| Reachable | 77 of 100 |
| Using the obfuscation | **10 of 77 = 13.0%**, 95% Wilson [7.2%, 22.3%] |
| Hiding an address found nowhere else on the page | 9 of 77 = 11.7% |

Split by entity, it lands where the tool is aimed:

| Entity | Using it |
|---|---|
| **Municipality** | **6 of 16 = 37.5%** [18.5%, 61.4%] |
| Company | 4 of 59 = 6.8% [2.7%, 16.2%] |

`seed_discoverer` hardcodes a municipality list, `scripts/muni_rm_scan.py`
exists to sweep the Región Metropolitana's 52 comunas, and [PRD.md](../PRD.md)
names municipal directory conventions as a reason the tool is Chile-specific.
What came back is the shape of address the tool exists for:
`alcaldia@hualane.cl`, `partes@tome.cl`, `contacto@sanbernardo.cl`,
`contacto@requinoa.cl`. The two intervals overlap at n=77, so this is a
direction rather than a settled ratio.

**The decision this ADR actually records is not "decode it".** That much is
mechanical. It is why this measurement carried **no pre-registered threshold**,
in a version where the two features beside it were killed by thresholds
([ADR-0019](0019-the-sibling-cl-hint-is-measured-and-declined.md),
[ADR-0020](0020-a-convenience-sample-overstated-a-source-400-times.md)). Read
without that reasoning, v0.60 looks like a version that gated what it wanted to
decline and waived the gate on what it wanted to build.

## Decision
**A source needs a gate. A parser does not.**

A *source* spends something per scan that is independent of whether it pays
off: the sibling `.cl` hint cost a DNS query on every non-`.cl` target, the PGP
keyserver source would have cost an HTTP request on every scan, and the curated
stage [ADR-0013](0013-curated-source-stage-removed-after-measurement.md)
removed cost 3 to 4 fetches and up to 6.8 seconds. That expenditure is why a
threshold is needed: below some yield the request is waste, and the only way to
know is to fix the number in advance and then look.

A *parser* reads markup already in memory. It costs a regex over bytes the
crawler has fetched anyway, it cannot produce an address that was not published
on the page, and it never fires on a site that does not use the encoding. There
is no rate at which it becomes harmful, so a pre-registered threshold would
have nothing to decide and would be theatre.

**The measurement still runs, and still comes first.** Not to gate the work but
to keep the record honest: whether the figure is 2% or 40% changes how this
decision reads, and asserting it without checking is precisely the habit
ADR-0020 was written about. The number is reported with its interval, its
non-response and its limits, the same as every other in this version.

**Decoding widens how addresses are read, never which ones count.** A decoded
non-`.cl` address stays out of scope, unchanged from
[ADR-0014](0014-country-is-never-inferred-from-a-com-address.md) and
[ADR-0018](0018-generation-stays-in-cl-and-a-guess-says-so.md).

**Payloads are read off the DOM attribute rather than the raw HTML**, so
decoded addresses pass through the same visible-versus-hidden split
[ADR-0021](0021-an-address-a-reader-cannot-see-is-not-a-contact.md)
introduced. An obfuscated address planted inside a `display:none` container is
still a trap, and decoding it does not launder it.

## Consequences
- RadarCL recovers addresses on roughly one in eight reachable Chilean
  institutional homepages that it previously could not see at all, and on
  something closer to one in three municipal ones.
- **The homepage figure is a floor for what a scan recovers.** This measured
  whether a site uses the encoding, over one page. A real crawl visits dozens
  of pages per domain, so addresses recovered per scan should exceed the nine
  counted here. Not measured, and not claimed.
- **23% of the sample was unreachable**, mostly connection refusals and two
  403s. That skews toward sites hostile to crawlers, which are plausibly the
  same sites more likely to deploy anti-harvesting, so 13% probably understates
  prevalence rather than overstating it.
- **A defect was caught that a unit test would have missed.**
  `csdcolocolo.cl` encodes the whole `mailto:` target, query string included,
  so the raw decode yields `ventas@csdcolocolo.cl?subject=Asistencia...`. A
  test written with a clean address would have passed. The decoder splits on
  `?` exactly as the plain `mailto:` branch already did. This is the practical
  case for measuring against real pages before wiring anything.
- `extract_emails` gains two module-level helpers, `find_cf_payloads` and
  `decode_cf_email`, which `scripts/cloudflare_email_prevalence.py` imports.
  The harness and the shipped code share one decoder, so the measured number
  describes the behaviour that shipped.
- **This does not generalise to other obfuscation.** JavaScript-constructed
  addresses, canvas-rendered ones and CSS `direction: rtl` tricks are all in
  use and all remain invisible here, because reading them needs a DOM and a
  script engine. That gap is the same one ADR-0021 recorded for
  stylesheet-applied hiding, and it has the same answer: a headless browser,
  which [ADR-0005](0005-hardware-aware-auto-tuning.md)'s low-spec target rules
  out.
- No new dependency. The offline suite grows 168 to 174.

## Alternatives considered
- **Pre-register a threshold anyway**, for consistency with the two items
  beside it. Rejected because consistency of ritual is not consistency of
  reasoning: a gate exists to stop a per-scan cost that cannot be recovered,
  and this has none. Applying one would have meant inventing a number nobody
  could justify and then either honouring it against sense or waiving it,
  which is worse than not setting one.
- **Skip the measurement and just build it**, since no gate would ride on it.
  Rejected: the ADR would then rest on an assumption about prevalence, and the
  municipality finding - the most useful thing the run produced - would never
  have surfaced.
- **Regex the raw HTML for payloads**, which is simpler than walking the DOM.
  Rejected because it bypasses ADR-0021's hidden-markup split, so a trap
  planted as an obfuscated span would be decoded and reported as an ordinary
  visible address.
- **Decode in the crawler instead**, rewriting pages before extraction. Bigger
  blast radius, and it would put an understanding of one CDN's markup into the
  layer that only fetches bytes.
- **Handle JavaScript-constructed addresses too**, which the same research
  found are what actually works against scrapers in 2026. Rejected as a
  different project: it requires the headless browser this crawler
  deliberately does not run.
