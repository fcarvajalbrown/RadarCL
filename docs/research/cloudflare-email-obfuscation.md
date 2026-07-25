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

*Results are appended below this line once the run completes. Nothing above
it is edited afterwards.*
