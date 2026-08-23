# 0018 - Generation stays in `.cl`, and a guess says so

## Status
Superseded by [0024](0024-scope-follows-the-target-domain.md) on scope; its
second decision, that `generated` travels with the record, stands. Narrows
[0014](0014-country-is-never-inferred-from-a-com-address.md).

## Date
2026-07-25

## Deciders
Felipe Carvajal Brown

## Context
[ADR-0014](0014-country-is-never-inferred-from-a-com-address.md) decided that a
non-`.cl` address may be produced when the user names that domain, keeping the
pattern-generation path rather than removing it. Two things about that turned
out to be wrong.

**The capability never worked.** `crawl_and_extract` emitted
`jimmy.nunez@bhp.com` as promised, but `verifier._SYNTAX_RE` hard-codes
`\.cl$`, so `verify()` rejected every one of them at stage 1 and recorded
`status: invalid, error: "Invalid email format"`. The address is perfectly
well-formed; what disqualified it was scope. So the path generated candidates
it could never verify, and told the user something false about why.

**ADR-0014 overstated the harm, and this ADR corrects it rather than editing
it.** Its Context says the leak put `sarah.wilson@bhp.com` "in a file labelled
Chilean contacts". The address reached the discovery stream and the JSON and
HTML run record; it never reached the CSV, because the syntax stage rejected it
before verification and the CSV carries VALID only. The decision ADR-0014 made
does not depend on the difference, but the record should not claim more than
was measured. ADR-0014's Status line is unchanged and its text stands.

**The real question was whether a `.com` address can be tied to a country at
all.** Not inferred from a page, which ADR-0014 settled, but *anchored*: is
there a domain whose staff are Chilean by construction? Measured on
2026-07-25 across thirteen companies, asking whether each runs a mail-capable
`<company>.cl`:

| Has a `.cl` mail domain | No `.cl` mail domain |
|---|---|
| riotinto, angloamerican, teck, glencore | bhp, sqm |
| codelco, falabella, cencosud, arauco | latamairlines, albemarle, sonda |

**Eight of thirteen, including four of the six foreign multinationals with
Chilean operations.** Rio Tinto's Chilean staff are reachable at
`riotinto.cl`, Anglo American's at `mail.angloamerican.cl`, Teck's at
`emailproxy.teck.cl`. Those are anchored by the ccTLD itself, need no
attribution, and fall entirely inside the scope RadarCL already supports.

This is a different use of the sibling `.cl` than ADR-0014 rejected. There it
was proposed as *evidence that a `.com` page is Chilean* and measured at 56%
false positives. Here nothing is inferred about any address: it is a better
target, not a claim.

BHP remains the honest exception. `bhp.cl` does not exist, so there is no
country-anchored domain, and nothing distinguishes a colleague at Escondida
from one in Melbourne. `bhp.com` also refuses the crawler outright.

**Separately, no export said which addresses were invented.**
`Discovery.generated` existed and stopped at `verify_all`, so a harvested
address and a pattern guess were indistinguishable in every output file.

## Decision
**Pattern generation is held to the same `.cl` scope as scraping.** The
generated branch in `crawl_and_extract` now requires a `.cl` target. This
reverses ADR-0014's "explicit, user-named, no country claim" for the generated
path, on evidence that arrived after it: the path never functioned, and where a
company has Chilean staff it usually has a `.cl` mail domain that works today.
`PRD.md`'s scope boundary is now true in code, not only in prose.

Nothing is lost that worked. Anyone who wants Rio Tinto's Chilean staff targets
`riotinto.cl` and gets the full pipeline, verification included.

**`generated` travels with the record and appears in JSON and HTML.** A
pattern guess and a published address are different kinds of claim, and an
export that renders them identically is the overclaiming
[ADR-0017](0017-a-reply-is-evidence-only-about-its-subject.md) exists to
prevent. The HTML report marks such rows; the CSV keeps the columns
[ADR-0010](0010-export-contents-differ-by-format.md) gave it. The key is
omitted rather than set false when the caller had no provenance to report, the
same absent-versus-empty distinction ADR-0014 drew for evidence.

## Consequences
- A user who runs `--target-domain bhp.com --pattern ...` now gets nothing
  instead of unverifiable candidates labelled with a false reason. That is a
  reduction in output and an increase in what the output means.
- The `.com` question is closed in both directions: not by inference
  (ADR-0014), and not by generation either. What remains is targeting the `.cl`
  domain, which was always the supported path.
- **RadarCL does not tell the user that `riotinto.cl` exists when they ask for
  `riotinto.com`.** The measurement says that hint would help on eight of
  thirteen companies. It is not built here, and it is the obvious next thing.
- `verify_all` now accepts tuples of two, three or four elements. That
  tolerance is load-bearing for the `verify` subcommand, which reads bare
  addresses and has neither a page nor a provenance.
- The sample is thirteen companies chosen because they came up in earlier
  measurements, not drawn at random. It is enough to show the `.cl` mail domain
  is common, not enough to put a number on how common.

## Alternatives considered
- **Make `.com` generation work**, by letting the syntax stage accept any
  domain the user named. It would serve the real Chile-based staff at BHP.
  Rejected because it would have RadarCL produce verified-looking foreign
  addresses with nothing between the user and a colleague in Melbourne but
  their own judgement, and because for eight of thirteen companies the
  country-anchored domain already exists.
- **Keep the behaviour, fix only the error message** to say "outside `.cl`
  scope" rather than "Invalid email format". The smallest honest change.
  Rejected because it preserves a path that generates what it cannot verify,
  which is a feature in name only.
- **Exclude generated addresses from the CSV entirely**, even when VALID.
  Rejected because it removes the entire payoff of pattern generation, which is
  finding addresses nobody published; the marker in JSON and HTML carries the
  caveat without discarding the result.
- **Amend ADR-0014 in place** to fix its overstatement. Rejected: immutability
  exists precisely so a record cannot be tidied after the fact, and the
  correction is more useful attached to the decision that acts on it.
