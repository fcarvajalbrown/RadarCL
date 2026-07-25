# 0021 - An address a reader cannot see is not a contact

## Status
Accepted

## Date
2026-07-25

## Deciders
Felipe Carvajal Brown

## Context
Both of v0.60's planned items were declined on measurement
([ADR-0019](0019-the-sibling-cl-hint-is-measured-and-declined.md),
[ADR-0020](0020-a-convenience-sample-overstated-a-source-400-times.md)),
leaving the version empty. Reading how commercial email-finders actually work
- Hunter, Apollo, RocketReach, Snov, Skrapp - turned up a defect in RadarCL
rather than a missing feature.

**RadarCL harvests spam traps.** `extract_emails` ran `soup.get_text()` over
the whole document and iterated every `<a href>`, so anything in the markup was
collected regardless of whether a reader could see it. Checked against crafted
markup before anything was changed, five of six honeypot placements were
extracted; the implementation now recognises eight:

| Placement | Was collected |
|---|---|
| `display:none` container | yes |
| `visibility:hidden` | yes |
| `opacity:0` | yes |
| text painted the same colour as its background | yes |
| `font-size:0` on the anchor itself | yes |
| off-screen `text-indent:-9999px` | yes |
| `aria-hidden="true"` | yes |
| HTML5 `hidden` attribute | yes |
| `<script>`, `<style>`, HTML comments | no - BeautifulSoup already excludes these |

A honeypot is *defined* by that placement. It is an address that has never
belonged to a person and was never published anywhere a human would submit it;
it sits in hidden markup precisely so that anyone who mails it identifies
themselves as having harvested rather than been given the address. Mailing one
is grounds for immediate listing by operators such as Spamhaus, and that
listing attaches to the sending domain, so it costs the user every other
address in the file rather than just the trap.

These addresses reached the CSV, which
[ADR-0010](0010-export-contents-differ-by-format.md) defines as the mailable
deliverable and which the GUI writes to the user's Desktop automatically at the
end of a run. That is the same failure shape as
[ADR-0016](0016-catch-all-domains-are-not-valid.md): something unverifiable
placed in the one output whose entire value depends on not guessing. It is
worse in one respect. A catch-all address that bounces costs a bounce; a trap
costs the domain.

**The tension this ADR has to settle** is that RadarCL already has a precedent
pointing the other way.
[ADR-0014](0014-country-is-never-inferred-from-a-com-address.md) established
that page-level provenance signals annotate and never filter, because at 57%
recall a filter would silently discard real addresses on 43% of Chilean sites.
Applied literally, that says hidden addresses should be flagged and kept
everywhere, including the CSV.

## Decision
**An address found only in markup a reader cannot see is flagged, kept in the
run record, and excluded from the CSV.**

This reconciles both precedents rather than choosing between them, and needs no
new principle: ADR-0010 already makes the CSV the mailable list and the JSON and
HTML the run record, and ADR-0016 already excludes a category from the CSV on
exactly this reasoning. ADR-0014's objection was to a *silent* filter that
discards evidence; nothing is discarded here. The user sees the address, sees
that it was hidden, and sees why it was held back.

**The flag is set only when every occurrence on the page was hidden.** Sites
repeat a contact address inside collapsed menus, print-only blocks and
accessibility duplicates constantly. One visible occurrence settles the
question, so `contacto@nunoa.cl` appearing in both a contact block and a
`display:none` div is a contact, not a trap.

**Only the element's own attributes are read.** Hiding applied from a
stylesheet, or set later by script, is not detected. Resolving that needs a CSS
engine and a live DOM, which is the headless-browser cost this crawler
deliberately does not pay and which
[ADR-0005](0005-hardware-aware-auto-tuning.md)'s low-spec target rules out.
The detection is therefore a floor, not a guarantee.

**No measurement was run before this shipped, and that is a departure.** Every
other item in v0.60 was pre-registered and measured, and this one was not: the
defect was already demonstrated against crafted markup, and unlike a candidate
source, any non-zero rate of traps in the CSV is a defect rather than a number
to weigh. The decision was made on that basis. **What is therefore unknown is
how often `.cl` sites actually plant them** - the fix could be protecting
against something that never occurs in this population, and nothing here shows
otherwise. That is recorded rather than implied, because the rest of this
version's record would otherwise suggest a number exists.

## Consequences
- **Some real addresses will be kept out of the CSV.** A site that hides a
  genuine contact behind a collapsed menu implemented with inline
  `display:none`, and nowhere else, now loses that address from the mailable
  list. It stays in the JSON and HTML with the marker. The trade is deliberate
  and asymmetric: a real address wrongly held back is recoverable from the run
  record, and a trap wrongly mailed is not recoverable at all.
- **A trap discovered before its visible twin stays marked.**
  `crawl_and_extract` deduplicates across the whole crawl and the first
  occurrence wins, so an address that a hidden div on page 1 carries and a
  contact block on page 40 also carries is reported hidden. Per-page the logic
  is right; across pages it errs toward caution, which is the direction chosen
  deliberately.
- `extract_emails` returns a third key, `hidden`. Any outside caller of
  `app/core/` as a library sees a new field; nothing existing changes meaning.
- **`Discovery` gains a field and the Qt signals gain an argument.**
  `CrawlerWorker.email_found` and `candidate_found` go from
  `Signal(str, str, object)` to `Signal(str, str, object, bool)`. The GUI was
  the layer that actually needed this: it writes a CSV to the Desktop
  automatically, and it was the only consumer that could not have been fixed by
  the CLI alone.
- **The GUI now also carries `generated` into its exports**, which it never did
  - it passed three-element tuples where the CLI passed four. That is fixed as
  a side effect of widening the same call, so ADR-0018's marker finally reaches
  GUI runs.
- The results table is unchanged. A hidden address looks like any other there,
  which is consistent with ADR-0014 leaving evidence out of that table, and it
  means the GUI user learns about the exclusion from the HTML report rather
  than from the screen. Worth revisiting if it confuses anyone.
- The offline suite grows from 153 to 168: one case per hiding technique, plus
  the visible-twin case and the CSV exclusion.
- No new dependency. `vendor/`, `SHA256SUMS.txt` and `requirements-core.lock`
  are untouched.

## Alternatives considered
- **Never extract hidden addresses at all**, dropping the subtrees before
  extraction runs. The smallest diff by a wide margin. Rejected because it is
  the silent filter ADR-0014 argued against: the run record would lose the fact
  that a page carried a trap, which is real signal about that site, and a user
  comparing two runs would see addresses vanish with no explanation anywhere.
- **Flag them and leave them in the CSV**, following ADR-0014's flag-not-filter
  line strictly. Rejected because the CSV's entire purpose is addresses that
  can be mailed, and a marker in a column nobody reads before a mail merge is
  not protection. This is the case ADR-0016 already decided in the same
  direction.
- **A `--include-hidden` switch.** Rejected as configuration for a value that
  should never change, and because shipping a switch whose enabled position is
  a footgun invites exactly one support question.
- **Measure `.cl` honeypot prevalence first**, as v0.60's other two items were
  measured. Weighed and not taken: the defect is demonstrated, the harm is
  asymmetric, and unlike a candidate source there is no number at which
  collecting traps becomes acceptable. The cost is recorded above as an
  unknown rather than treated as settled.
- **Render pages in a headless browser** so stylesheet-applied and
  script-applied hiding is caught too. Rejected on ADR-0005's hardware
  constraint and on scope: it would replace the crawler rather than extend it.
  It is the only way to close the gap this ADR leaves open, and it is not worth
  that price on evidence nobody has yet.
