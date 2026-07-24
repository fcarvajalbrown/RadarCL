# 0010 - Export contents differ by format: CSV is the mailable list, JSON and HTML are the run record

## Status
Accepted

## Date
2026-07-24

## Deciders
Felipe Carvajal Brown

## Context
Until v0.35 RadarCL wrote exactly one output format. `export_valid()` filtered
on `status == 'valid'` and wrote four columns to CSV, and that filter was
never a decision anyone made - with a single format there was nothing to
decide. [ADR-0004](0004-verification-staging-unknown-not-invalid.md) simply
recorded it as a fact about the code.

Adding JSON and HTML forces the question the single-format design let us
avoid: what is an export *for*? Two answers are defensible.

- A **deliverable**: the addresses you can act on. Everything else is
  working material and belongs nowhere near the file you hand to someone.
- A **record of the run**: what was found, what each address turned out to
  be, and why. The verdicts that are not VALID are most of what the tool
  actually produced.

[ADR-0004](0004-verification-staging-unknown-not-invalid.md) and
[ADR-0009](0009-mx-resolution-failure-is-unknown.md) both establish that
UNKNOWN is a first-class outcome and not a soft INVALID - an address nobody
could check, usually because the mail server refuses verification probes or
because a DNS lookup went unanswered. A valid-only export discards every one
of them along with the `error` string explaining why, which is precisely the
information needed to decide what to retry.

The bug behind ADR-0009 makes the cost concrete. On that machine every
`nunoa.cl` address resolved to a DNS failure. Under a valid-only export the
resulting file would have been empty, and the reason - a resolver timeout,
not a dead domain - would have existed only in the GUI's table until the
window closed.

Against that, the existing CSV is the file that gets opened in a spreadsheet
and mailed. Widening it means an operator who has been copying column A for
months silently starts copying unverified addresses.

## Decision
Format determines contents, and the two answers above are both honoured
rather than reconciled.

| Format | Contents | Rationale |
|---|---|---|
| CSV | VALID only, unchanged | The deliverable. Existing behaviour, existing consumers. |
| JSON | Every record, with `status` and `error` | The run record, for machines. |
| HTML | Every record, with `status` and `error` | The run record, for people. |

**CSV is untouched.** Same filter, same four columns, and the GUI's
post-verification auto-export to `~/Desktop/RadarCL-YYYY-MM-DD.csv` still
writes CSV and nothing else. No existing invocation changes behaviour.

**JSON** is an object rather than a bare array, carrying `tool`, `version`,
`exported_at`, a `summary` count block and the `results` list. The wrapper
exists so the summary and the tool version travel with the data instead of
each consumer re-tallying rows to learn how the run went.

**HTML** is a single self-contained file: inline CSS, no JavaScript, no
external stylesheet, font or image. It has to open and read correctly on a
machine with no network, which is the same stance
[ADR-0008](0008-vendored-core-dependencies.md) takes on dependencies. It
carries the per-status counts, the full table, and a note stating in plain
Spanish that Desconocido does not mean inválido - the report is where that
distinction has to survive contact with someone who did not read this ADR.

**Format selection** is by output extension (`.csv`, `.json`, `.html`,
`.htm`), overridable with `--format`. An unrecognised extension with no
`--format` is an error, raised before any crawling or verification starts
rather than after it. CLI and GUI both go through one `export()` entry point
so the rule lives in one place.

## Consequences
- Two exports of the same run legitimately disagree on row count. That is
  the point of the decision, and it is why this ADR exists rather than the
  behaviour living only in a docstring.
- The `error` field now leaves the machine. It can contain SMTP server text
  and resolver messages, which is diagnostic detail that was previously
  GUI-only. It goes only where the user explicitly writes a JSON or HTML
  file, never to the Desktop auto-export.
- The HTML report renders strings harvested from crawled pages, so every
  cell is escaped and a source URL becomes a link only when its scheme is
  `http` or `https`.
- No new dependency: `csv`, `json` and `html` are all standard library, so
  `vendor/` and `requirements-core.lock` are unaffected
  ([ADR-0008](0008-vendored-core-dependencies.md)).
- `app/core/exporter.py` imports `app.__version__` to stamp exports. That is
  a dependency from `core` up to the package root, which holds nothing but a
  version string and no imports of its own, so the Qt-free boundary
  ([ADR-0002](0002-async-core-qthread-worker-bridge.md)) is unaffected.
- The GUI's export button no longer means "save the valid ones", so it is
  labelled `Exportar…` and its dialog names what each filter contains.

## Alternatives considered
- **All three formats VALID-only**: exact parity with today, no new
  semantics, and nothing to document. Rejected because it makes the HTML
  report nearly pointless - a page listing only successes answers no
  question the CSV did not already answer, and it would have rendered empty
  on the machine that produced ADR-0009.
- **All three formats carry everything, CSV included**: one rule, no
  asymmetry, easiest to explain. Rejected because the CSV is the file people
  already treat as the mailing list. Quietly adding INVALID rows to it
  invites someone to mail addresses the tool just established are dead.
- **A `--include-invalid` flag deciding per run, for every format**:
  maximally flexible. Rejected because it makes the meaning of a file depend
  on a flag that is not recorded in the file, so a JSON received second-hand
  cannot be interpreted without knowing how it was produced. Tying contents
  to the extension makes every file self-describing.
- **A bare JSON array of records**: simpler to consume with `jq` and the
  more common convention. Rejected because it has nowhere to put the summary
  or the tool version, and the summary is what makes an export readable
  without processing it first.
