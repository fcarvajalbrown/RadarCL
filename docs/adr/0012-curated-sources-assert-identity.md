# 0012 - Curated sources assert their identity, not just their availability

## Status
Superseded by [0013](0013-curated-source-stage-removed-after-measurement.md)

## Date
2026-07-24

## Deciders
Felipe Carvajal Brown

## Context
[ADR-0011](0011-ct-fallback-and-source-hygiene.md) replaced four curated
sources that had rotted and added a live test that refetches every entry. It
also recorded, in its own Consequences, the limit of that test:

> That test catches a source disappearing, not one quietly changing what it
> is, so a green run is weaker evidence than it looks: `munitel.cl` would
> have passed it while serving property listings.

That limit is the actual failure mode, not a hypothetical one. Every one of
the four removed sources except `fach.cl` was answering `200` while being the
wrong thing. A status-code check would have passed `munitel.cl`,
`transparencia.cl` and `cna.cl` every day for however long they had been
wrong, which is precisely how they survived unnoticed.

Two candidate methods were measured before choosing.

**Identity phrases**, the pattern uptime monitors sell as keyword monitoring
and position as the defence against content hijack: assert that a phrase
naming the institution is still on the page. Tested against the live list and
against the four removed sources:

| Sources | Result |
|---|---|
| The 12 curated URLs | 12 of 12 pass |
| `transparencia.cl`, `munitel.cl`, `cna.cl` | all three fail as DRIFTED |
| `fach.cl` | fails as UNREACHABLE |

**Similarity against a stored baseline**, from the Off-Topic Memento Toolkit
(Jones, Weigle and Nelson, Old Dominion University), whose published result is
cosine similarity at threshold 0.10 combined with word-count change at -0.85,
accuracy 0.987 and F1 0.906. Tested here against Wayback Machine snapshots:

| Pair | Cosine | Word count change |
|---|---|---|
| `transparencia.cl` 2021 against today, a source that rotted | 0.035 | +15.27 |
| `subdere.gov.cl` 2021 against today, a control | 0.722 | +0.18 |
| `subdere.gov.cl` 2022 against today, a control | 0.706 | -0.11 |

Both methods work and both are dependency-free. TF-IDF cosine is token
counting, a dot product and two square roots, so `collections.Counter` and
`math.sqrt` cover it; scikit-learn and gensim were priced at 57.5 MB and 73 MB
of vendored wheels against a 9.7 MB core and buy convenience rather than
capability. gensim is additionally LGPL-2.1 against this project's Apache 2.0,
which is a question for a lawyer and not one this ADR answers.

## Decision
**Every curated source declares a phrase its page must contain.**
`_KNOWN_SOURCES` becomes a mapping of URL to phrase rather than a list of
URLs, so a source cannot be added without one. Iterating the mapping still
yields its URLs, so `discover_seeds` is unchanged apart from its default.

Matching is on visible text: scripts and styles removed first, since an
analytics snippet can carry a word the page no longer says, then HTML
entities unescaped so a phrase can be written with its accents rather than as
`informaci&oacute;n`, then lowercased.

A phrase must name the institution rather than quote its navigation or its
current campaign. It has to survive a redesign and die with a change of
owner. Offline tests enforce what can be enforced mechanically: no empty
phrase, none lowercase-unstable, none drawn from a list of generic words, and
a URL appearing under two entity types must declare the same phrase in both.

**Similarity checking is not adopted.** It needs a committed baseline per
source that has to be refreshed whenever a site legitimately redesigns past
the threshold, and the phrase check already catches every failure actually
observed. The measurements are recorded above so the option can be taken up
later without redoing the work.

**The two failure kinds are reported separately.** UNREACHABLE is retried
once, because `subdere.gov.cl` threw a transient `RemoteProtocolError` during
this investigation and answered on the next call; a guard that goes red on a
network blip is a guard people learn to ignore, and being ignored is what
produced this ADR. DRIFTED is never retried: the page loaded and is no longer
what it was. Both fail the test. The assertion carries the message rather
than leaving it to `== []`, since naming which source went wrong is the whole
value of the check.

This narrows one consequence of [ADR-0011](0011-ct-fallback-and-source-hygiene.md).
Everything else that ADR decided stands, so it is not superseded.

## Consequences
- The failure that removed four sources is now caught by a test. Verified by
  running the guard against the list as it stood before v0.4.0: it reported
  `munitel.cl` and `cna.cl` as DRIFTED and `fach.cl` as UNREACHABLE, and
  passed `subdere.gov.cl`.
- Adding a source now requires opening its page and choosing a phrase. That
  is deliberate friction. The entire premise of this ADR is that sources were
  added and never looked at again.
- A phrase can go stale for an innocent reason. An institution that renames
  itself will fail the check, and the correct response is to read the page
  and update the phrase, which is the same work the check exists to prompt.
- The guard is still not complete. It catches a page that stops naming its
  institution; it would not catch one that keeps its name while its useful
  content moves behind a login. The similarity measurements above are the
  starting point if that turns up.
- `_KNOWN_SOURCES` changes shape from `dict[EntityType, list[str]]` to
  `dict[EntityType, dict[str, str]]`. Anything iterating it for URLs is
  unaffected; anything indexing it positionally would break, and nothing does.
- Still no new dependency. `html`, `re` and `httpx` were all present.

## Alternatives considered
- **Cosine similarity plus word count against a committed baseline**: the
  research-backed method, and the measurements above show it separates a
  rotted source from a five-year-old genuine one by 0.035 against 0.706.
  Rejected for now on maintenance cost, not on accuracy: it needs a baseline
  artifact per source and a refresh ritual after every legitimate redesign,
  to catch a class of drift that has not yet occurred here.
- **Both methods together**: phrase for identity, similarity for gradual
  drift. Rejected as buying a second signal for the same failure the first
  one already catches, at the cost of the baseline file.
- **scikit-learn or gensim for the vectorizer**: rejected on both weight and
  redundancy. 57.5 MB or 73 MB against a 9.7 MB vendored core, to replace
  twenty lines of standard library.
- **Negative keywords**, failing when commercial vocabulary appears: cheap,
  and would have caught `munitel.cl`. Rejected because it guesses at the shape
  of the next failure, and the next one will not be a property portal.
- **Only DRIFTED fails, UNREACHABLE skips**: never flaky. Rejected because a
  source vanishing outright would then fail nothing, discarding the check
  ADR-0011 already added.
- **No ADR, treated as ordinary test strengthening**: it is one column added
  to a data structure. Rejected because ADR-0011 states in writing that drift
  goes uncaught, and leaving that standing once the code catches it would
  make an Accepted ADR say something false.
