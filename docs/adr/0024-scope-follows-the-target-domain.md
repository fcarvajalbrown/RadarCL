# 0024 - Scope follows the target domain

## Status
Accepted. Supersedes [0018](0018-generation-stays-in-cl-and-a-guess-says-so.md)
on scope. ADR-0018's second decision, that `generated` travels with the record
into JSON and HTML, is untouched and reaffirmed below.

## Date
2026-08-22

## Deciders
Felipe Carvajal Brown

## Context
RadarCL cannot scan `bhp.com` or `gecamin.com`. Felipe named both as targets he
wants. The tool refuses both, and refuses them silently.

BHP is one of the thirteen companies with Chilean operations measured in
[ADR-0018](0018-generation-stays-in-cl-and-a-guess-says-so.md), and that
measurement found no `bhp.cl` to fall back to. Whether `gecamin.cl` exists has
not been checked here.

Asked to scan one, the tool crawls for minutes and reports zero. It is not a
refusal the user can see; it is five independent hardcoded `.cl` checks that
each produce silence:

| Place | What it does |
|---|---|
| `extractor.py:27`, `:32` | `_EMAIL_RE` and `_OBFUSCATED_RE` end in `\.cl\b`, so `@bhp.com` cannot be matched at all |
| `verifier.py:99` | `_SYNTAX_RE` ends in `\.cl$`, so a non-`.cl` address is INVALID at stage 1 |
| `pipeline.py:168` | pattern generation is skipped unless the target ends in `.cl` |
| `crawler.py:166`, `:265` | phase 1 follows links on `.cl` hosts only, so a `bhp.com` seed is fetched and the crawl then stops dead at it |
| `seed_discoverer.py:687` | the DuckDuckGo result regex captures `.cl` URLs only |

[ADR-0018](0018-generation-stays-in-cl-and-a-guess-says-so.md) put the third of
those there deliberately, and its reasoning was sound at the time. It rested on
two findings. First, the capability never worked: generation emitted
`jimmy.nunez@bhp.com` and `verifier._SYNTAX_RE` then rejected it as
`Invalid email format`, which is a false reason for a well-formed address.
Second, a measurement across thirteen companies found eight ran a mail-capable
`<company>.cl`, so for most targets the country-anchored domain already existed
and worked. ADR-0018 named BHP as the honest exception, because `bhp.cl` does
not exist.

The exception is the case. RadarCL's answer to the exception was to produce
nothing, and to produce it silently.

Two things separate this decision from the one ADR-0018 refused. **ADR-0018's
first finding was a bug report, not an argument.** `_SYNTAX_RE` rejecting a
well-formed address is a defect in the verifier; keeping the scope narrow so
that the defect is never reached is treating a symptom. **ADR-0018's objection
was about invention.** It rejected making `.com` generation work because RadarCL
would "produce verified-looking foreign addresses with nothing between the user
and a colleague in Melbourne but their own judgement". That objection is about
pattern generation, which invents an address from a name and a template. It does
not reach an address scraped off the target's own contact page, which is
something the site published.

[ADR-0014](0014-country-is-never-inferred-from-a-com-address.md) is not in
tension with this and stays Accepted. It forbids *inferring* a country from a
`.com` page. Nothing here infers anything: the user names the domain, and
`Discovery.evidence` reports per-page Chilean signals exactly as it does today,
with an empty tuple meaning checked-and-nothing-found.

## Decision
**Scope follows the target.** When the user names a target domain, an address at
that domain is in scope whatever its TLD. When the user names none, scope stays
`.cl`-only, which is what every existing scan does today.

This is one rule replacing five hardcoded ones. The extractor, the verifier's
syntax stage, the generation gate, the crawler's phase-1 host test and the
search-result regex all read the same scope rather than each carrying a copy of
`.cl`.

**A named target is an assertion by the user, not a claim by RadarCL.** The tool
returns what the domain published and says where it found it. It asserts nothing
about the country of the person behind the address, and ADR-0014's prohibition
on inferring one from a page is unchanged.

**Pattern generation is unlocked for a named non-`.cl` target, and a guess still
says so.** ADR-0018's second decision stands in full: `generated` travels with
the record and is marked in JSON and HTML, because a pattern guess and a
published address are different kinds of claim. That distinction is what carries
the caveat ADR-0018 was right to want, and it carries it without refusing the
target.

**Phase 1's scope becomes "the target domain or `.cl`", not "`.cl`".** Without
this the decision is inert: a `bhp.com` seed is fetched and its links are all
discarded, so the frontier empties and the crawl ends at the seeds. This changes
what phase 1 covers in
[ADR-0003](0003-crawl-phase1-phase2-scope.md); the two-phase structure itself,
narrow then optionally wide, is unchanged.

**No claim is made that this will find anything at `bhp.com`.** ADR-0018
recorded on 2026-07-25 that `bhp.com` "refuses the crawler outright". Whether
that is still true, and whether it is a wall
[ADR-0023](0023-a-wall-is-not-an-empty-site.md)'s detector now names, is
unmeasured. Removing a refusal RadarCL imposes on itself is worth doing whether
or not the site cooperates, and the two failures are now distinguishable in the
output, which they were not before.

## Consequences
- `scan bhp.com` and `scan gecamin.com` run the full pipeline: crawl, extract,
  optionally generate, verify. A non-`.cl` address can now reach the CSV, which
  ADR-0018 prevented.
- **The CSV can now carry a foreign address.** A scan of `bhp.com` that reaches
  a Melbourne contact page returns Melbourne addresses, and nothing in the file
  says the person is not in Chile. The user named the domain; `evidence` in the
  JSON and HTML run record is what reports the per-page signals, and the CSV
  keeps the columns [ADR-0010](0010-export-contents-differ-by-format.md) gave it.
  This is the exposure ADR-0018 closed, reopened knowingly and by request.
- The `.cl` default is unchanged. Every scan that works today produces the same
  result, and `RadarCL` remains a `.cl` tool for anyone who does not name a
  target outside it.
- `_SYNTAX_RE` stops being a scope check and becomes a syntax check, which is
  what its name says. The `Invalid email format` reason is now only ever given
  to an address that is actually malformed.
- **The five checks become one, so the next TLD costs nothing.** A `.mx` or
  `.co.uk` target works by the same rule without another decision. That is the
  reason a `.com` allowlist was rejected below.
- The off-domain reporting added alongside this still fires and matters more:
  scanning `bhp.com` discards any `.cl` address found on those pages, and the
  run summary now says so instead of folding it into a zero.
- Untouched, and still true: `detect_entity_type` misclassifies by substring,
  and honeypot and bot-wall prevalence on `.cl` remain unmeasured.

## Alternatives considered
- **Add `.com` to an allowed TLD list**, keeping `.cl` plus `.com` and perhaps
  `.org` and `.net`. The smallest diff, and it covers both targets that prompted
  this. Rejected because `.com` is not a category that means anything here: the
  list would still refuse a `.mx` or `.co.uk` target, and the same decision would
  have to be reopened the next time one came up. It also leaves five copies of a
  scope test in place instead of one.
- **Drop the TLD restriction entirely**, extracting every address from every
  crawled page and letting `chile_evidence` report per-page signals so the user
  filters afterwards. The most general and most future-proof. Rejected because it
  harvests foreign vendors, agency contacts and `newsletter@` by default on every
  scan, and because a tool whose default output is untargeted is a different
  tool.
- **Leave ADR-0018 standing and tell the user to target `<company>.cl`.** The
  status quo, and correct for eight of the thirteen companies ADR-0018 measured.
  Rejected because it is precisely wrong for the two companies asked about here,
  and because the failure mode is a silent zero rather than a message saying the
  domain is out of scope.
- **Fix only `_SYNTAX_RE`**, so a non-`.cl` address at least fails for a true
  reason. Honest and tiny. Rejected because nothing would then reach it: the
  extractor never matches the address in the first place.
