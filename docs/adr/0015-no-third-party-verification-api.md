# 0015 - No third-party verification API, and Stage 4 is removed

## Status
Accepted

## Date
2026-07-25

## Deciders
Felipe Carvajal Brown

## Context
`app/core/verifier.py` has carried a fourth verification stage since the
beginning, described in its module docstring as "API - optional third-party
(placeholder)". [ROADMAP.md](../../ROADMAP.md) listed resolving it under v0.55,
noting it was "an undecided placeholder, not a real deferred item".

It is more inert than that description suggests. Checked on 2026-07-25:

- **No interface exposes it.** `app/cli.py` has no `--api-key` flag, and
  `app/ui/control_panel.py` constructs `VerifierWorker` without passing one. No
  user of either the CLI or the desktop app can reach the stage.
- **Its output is read by nothing.** `VerificationResult.api_status` is set in
  one place and never consulted. It does not reach `pipeline.verify_all`'s
  record dict, so no exporter and no GUI table has ever seen it.
- **It cannot run on the path that would matter.** `verify()` returns early
  when `smtp_enabled` is false, before the stage, so it only fires when the SMTP
  handshake ran *and* left the status UNKNOWN.
- It sets the string `"not_implemented"` and returns.

The `api_key` parameter is threaded through `verify()`, `pipeline.verify_all`
and `VerifierWorker.__init__` to feed it.

No Accepted ADR currently asserts that this stage exists. It is described in
[ADR-0004](0004-verification-staging-unknown-not-invalid.md) and restated in
[ADR-0007](0007-smtp-response-classification.md), both superseded;
[ADR-0009](0009-mx-resolution-failure-is-unknown.md), which supersedes them, is
about MX classification and does not restate the stage list. So the placeholder
outlived the records that described it.

**What a real integration would cost, surveyed 2026-07-25.** Free tiers are 100
verifications a month (ZeroBounce, AbstractAPI) or 1,000 one-time
(NeverBounce); paid access runs about USD 0.008 per address. A single
`nunoa.cl` scan in this project found 26 addresses, so a free tier is spent
almost immediately in real use.

**What decides it is accuracy, not price.** Independent comparisons put every
provider at 70-85% on catch-all domains, and observe that providers claiming
better are generally answering "valid" to accept-all servers. Catch-all is the
open verification problem in this project, queued directly behind this decision.
Paying an external service to be unreliable on the exact case that motivates
verification work is not a trade worth making.

The open-source alternative, Reacher / `check-if-email-exists`, is AGPL, which
constrains reuse, and self-hosting it means issuing SMTP probes from the
operator's own address, which `verifier.py` already does.

## Decision
**No third-party verification API is planned.** This is a closed question
rather than a deferred item, and the roadmap says so instead of carrying it.

**Stage 4 is removed from the code**, not merely left undecided:
`VerificationResult.api_status`, the stage block in `verify()`, and the
`api_key` parameter in `verify()`, `pipeline.verify_all` and
`VerifierWorker.__init__` all go. The verifier is a three-stage pipeline:
syntax, MX, SMTP.

A parameter no interface exposes, feeding a stage that sets a field nothing
reads, is not a seam for future work. It is the appearance of one. Keeping it
is what let the placeholder be mistaken for a deferred feature across four
versions, and a future integration would need its own design regardless.

**Verification stays local and unpaid.** RadarCL runs its own probes from the
operator's machine against their own network, which is the same stance
[PRD.md](../PRD.md) takes in ruling out a hosted service and
[ADR-0008](0008-vendored-core-dependencies.md) takes on dependencies: the tool
should keep working when an external service does not.

This closes the question for RadarCL, not for anyone forking it. Nothing here
argues the commercial APIs are bad at what they do; the argument is that they
are weakest exactly where this project needs strength, and that a paid,
revocable dependency is the wrong shape for a tool built to run offline.

## Consequences
- `verify()` and `pipeline.verify_all` lose their `api_key` parameter. Both are
  public entry points of `app/core/` as a library, so this is a breaking change
  for any outside caller passing it. RadarCL is pre-1.0 and the parameter was
  inert, so a caller passing it was getting nothing; the change is recorded here
  rather than smoothed over.
- The verifier's docstring stops advertising a fourth stage, which is what a
  reader would otherwise take as an unfinished feature.
- v0.55 loses one of its two items and keeps the one that matters. Catch-all
  detection is unaffected by this decision and is where the accuracy problem
  actually is.
- Nothing changes about what any user sees. No status, export, or GUI element
  ever depended on the stage.
- If a third-party API is ever wanted, it needs a new ADR and a real design.
  That is the point of removing the stub rather than keeping it: the next person
  should start from the question, not from a parameter someone left behind.

## Alternatives considered
- **Close the question but leave the parameter in place**, so a future
  integration has somewhere to attach. Rejected because the parameter is exactly
  what made a decision look like a deferral, and an integration designed later
  would not be constrained by a signature chosen now.
- **Build the integration.** It would add a signal independent of RadarCL's own
  SMTP probe, which has real value where a mail server blocks the operator
  specifically. Rejected on the measured accuracy on catch-all domains and on
  the dependency shape: an API key, a paid quota, terms nobody has read, and a
  service that can change or disappear, in a project that vendors its wheels to
  survive precisely that.
- **Self-host Reacher / `check-if-email-exists`.** Rejected on the AGPL
  constraint and because self-hosting reproduces what `verifier.py` already
  does, probing from the operator's own address, without addressing catch-all
  any better.
- **Leave the placeholder alone and say nothing.** The status quo. Rejected
  because it survived four versions being mistaken for planned work, and the
  cost of that is paid by whoever reads the module next.
