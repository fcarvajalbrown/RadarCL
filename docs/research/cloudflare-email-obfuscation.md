# How often do `.cl` sites hide addresses behind Cloudflare?

Research notes for [ROADMAP.md](../../ROADMAP.md)'s v0.60 item, decoding
Cloudflare's email obfuscation in `app/core/extractor.py`.

**This half is a pre-registration**, committed before any page was fetched.

Dated 2026-07-25.

## The mechanism, read rather than assumed

Cloudflare's Scrape Shield replaces a `mailto:` link with an anchor pointing
at `/cdn-cgi/l/email-protection#<hex>`, and inline addresses with a
`<span class="__cf_email__" data-cfemail="<hex>">`. The payload is a
single-byte XOR cipher whose **key is the first octet of the ciphertext**:
take the first two hex characters as the key, then XOR every subsequent byte
with it.

Cloudflare's own framing is that this is not encryption. The published
analyses put it plainly: storing the key next to the ciphertext is barely
better than sending the address in plaintext, and the point is only to be
*"enough to throw off the basic scripts that hunt for `mailto:` links"*.

**RadarCL is one of those basic scripts.** `extract_emails` already
de-obfuscates the `user [at] domain.cl` convention, which is the same job
against a form that was common a decade ago. This is the form actually
deployed now.

## Why this is measured but not gated

The two features declined in this version, the sibling `.cl` hint
([ADR-0019](../adr/0019-the-sibling-cl-hint-is-measured-and-declined.md)) and
the PGP keyserver source
([ADR-0020](../adr/0020-a-convenience-sample-overstated-a-source-400-times.md)),
each carried a pre-registered threshold that killed them. This one does not,
deliberately, and the reason is recorded so it is not mistaken for
inconsistency.

Those were **sources**: each cost a request per scan and had to earn it, so
a low yield meant the request was waste. This is a **parser**. It costs
nothing per scan beyond a regex over markup already in memory, it cannot
produce an address that was not published on the page, and it never fires on
a site that does not use Cloudflare. There is no rate at which it becomes
harmful, so there is nothing for a gate to decide.

What the measurement is for is the ADR: whether the number is 2% or 40%
changes how the decision reads, and guessing it would be exactly the
convenience-sample habit ADR-0020 was written about.

## Frame and sample

**Frame:** the 1597 registrable `.cl` domains of Wikidata organisations with
`P17` = `Q298`, the same pool used for the catch-all and PGP draws, with the
notability bias documented in
[sibling-cl-prevalence.md](sibling-cl-prevalence.md).

**Draw:** n = 100, `random.Random(20260727).sample(sorted(pool), 100)`, in
`scripts/data/cloudflare_cl.txt`.

**Method:** one GET of `https://<domain>/` per domain, redirects followed,
rate-limited. Homepage only — this measures whether a site uses the feature,
not how many addresses are behind it across the whole site, and the
difference is stated in the results rather than blurred.

## Reported

- Reachable and unreachable counts, non-response kept separate from "does not
  use it", the distinction [ADR-0009](../adr/0009-mx-resolution-failure-is-unknown.md)
  exists for.
- Share of reachable homepages carrying `__cf_email__` or
  `/cdn-cgi/l/email-protection`, with a 95% Wilson interval.
- **Addresses actually recovered**: how many `.cl` addresses the decoder
  yields that the current extractor misses on those same pages. That is the
  number that matters, and it can be lower than the prevalence figure if
  sites obfuscate addresses the page also prints in clear.

---

*Everything above was committed in `9b405b4` before the first page was
fetched. Below is the run.*

# Results, 2026-07-25

| | |
|---|---|
| Domains drawn | 100 |
| Reachable | 77 |
| Unreachable | 23 — 17 `ConnectError`, 4 `ConnectTimeout`, 2 × HTTP 403 |
| **Using Cloudflare obfuscation** | **10 of 77 = 13.0%, 95% Wilson [7.2%, 22.3%]** |
| **Yielding an address the extractor misses** | **9 of 77 = 11.7%, [6.3%, 20.7%]** |
| Addresses recovered, homepages only | 9 |

One in eight reachable Chilean institutional homepages hides at least one
address behind this, and almost all of those hide an address that is
nowhere else on the page.

## It pays off where the tool is aimed

| Detected entity | Using it |
|---|---|
| **Municipality** | **6 of 16 = 37.5%, [18.5%, 61.4%]** |
| Company | 4 of 59 = 6.8%, [2.7%, 16.2%] |
| Government | 0 of 1 |
| University | 0 of 1 |

**Municipalities use it five times as often as companies.** They are also
RadarCL's primary target: `seed_discoverer` carries a hardcoded
`_CL_MUNICIPALITIES` set, `scripts/muni_rm_scan.py` exists to sweep all 52
comunas of the Región Metropolitana, and [PRD.md](../PRD.md) names municipal
directory conventions as a reason the tool is Chile-specific at all.

The two intervals overlap, so on n=77 this is a strong indication rather
than a settled ratio. The point estimate is what it is, and the direction
matters more than the exact multiple.

What was recovered is exactly the kind of address the tool exists to find:

```
alcaldia@hualane.cl              contacto@requinoa.cl
partes@tome.cl                   contacto@sanbernardo.cl
municipalidadmariaelena@imme.cl  comunicaciones@salesianoconcepcion.cl
achs@achs.cl                     mackay_informaciones@mackay.cl
```

## A parsing defect the measurement caught

`csdcolocolo.cl` decoded to:

```
ventas@csdcolocolo.cl?subject=Asistencia%20tienda%20-%20csdcolocolo.cl
```

The obfuscated payload holds the whole `mailto:` target, query string
included, so a decoder that returns the raw string produces an address with
`?subject=...` welded on. The existing `mailto:` branch already splits on
`?`; the decoded branch has to do the same.

This is the practical argument for measuring before wiring: the unit test
would have used a clean address and passed.

## Limits

- **Homepages only.** This measures whether a site uses the feature, not how
  many addresses sit behind it across a whole site. A real crawl visits
  dozens of pages per domain, so the addresses recovered per scan should be
  higher than the nine here. Not measured.
- **23% unreachable**, and not at random: 403s and connection refusals skew
  toward sites that dislike crawlers, which are plausibly the same sites more
  likely to deploy anti-harvesting measures. If anything this understates
  prevalence.
- **One date, one network**, and Cloudflare adoption moves.
- The entity split rests on `detect_entity_type`, which
  [ADR-0020](../adr/0020-a-convenience-sample-overstated-a-source-400-times.md)
  records misclassifying a football club as a university. Here it had 16
  municipalities to work with and the domains are recognisably municipal
  (`hualane.cl`, `requinoa.cl`, `tome.cl`, `sanbernardo.cl`), so the
  municipal bucket is trustworthy even though the classifier is not in
  general.

## Verdict

No threshold was pre-registered and none is applied. At 13% of reachable
sites and 37.5% of municipalities, the parser is plainly worth the regex it
costs, and it is built.
