# 0007 - SMTP response classification by reply-code class

## Status
Superseded by [0009](0009-mx-resolution-failure-is-unknown.md)

## Date
2026-07-24

## Deciders
Felipe Carvajal Brown

## Context
[ADR-0004](0004-verification-staging-unknown-not-invalid.md) established
staged verification with UNKNOWN as a first-class outcome, and ruled that
only a syntax or MX failure sets INVALID while "an SMTP exception, timeout,
or non-250 response" results in UNKNOWN.

That rule is coarser than the protocol it describes. RFC 5321 divides reply
codes into transient 4xx failures, where a retry is expected, and permanent
5xx failures. Greylisting returns 450 or 451; rate-limiting returns 421. A
550 5.1.1 in response to RCPT TO is defined as "Bad destination mailbox
address" and is the canonical signal that a mailbox does not exist. Reply
code 252 means the server states outright that it cannot verify the address.

Collapsing all of these into a single non-250 bucket discards the one
genuinely informative negative signal SMTP provides. ADR-0004's own Context
justified UNKNOWN by naming servers that "greylist, rate-limit, or flatly
refuse" probes - greylisting and rate-limiting are both 4xx, so the
reasoning pointed at the 4xx class while the wording covered everything.

The code never implemented ADR-0004 as written in any case:
`app/core/verifier.py` set INVALID on every non-250, which is the opposite
of that ADR's rule and produced false negatives on real addresses behind
greylisting servers.

## Decision
`verify()` keeps ADR-0004's staging - syntax regex, DNS MX lookup, SMTP
`RCPT TO` handshake with no mail sent, then an optional API stage (currently
a placeholder) - stopping at the first definitive failure. A hard syntax or
MX failure sets INVALID. The SMTP stage classifies by reply-code class:

| Reply code | Status | Reason |
|---|---|---|
| 250 | VALID | Recipient accepted. |
| 5xx | INVALID | Permanent failure per RFC 5321. |
| 4xx | UNKNOWN | Transient; a retry is expected. |
| anything else, including 252 | UNKNOWN | Server states it cannot verify. |

An SMTP exception or timeout remains UNKNOWN, unchanged from ADR-0004. The
GUI's "Quick" vs "Deep" setting still only toggles whether the SMTP stage
runs at all (`smtp_enabled`).

## Consequences
- Greylisted and rate-limited addresses are no longer misreported as
  invalid, which was the specific false-negative ADR-0004 existed to prevent
  and which the code was producing anyway.
- SMTP can now produce INVALID, which ADR-0004 as written forbade. A server
  explicitly reporting that a mailbox does not exist is recorded as such
  rather than discarded as no information.
- `exporter.export_valid()` still keys off `status == 'valid'`, so the
  exported CSV is unaffected in shape. Its contents change only in that
  fewer real addresses are wrongly excluded.
- Known limitation: some servers return 550 for greylisting instead of the
  correct 451, so 5xx is strong evidence rather than proof. Addresses
  classified INVALID via SMTP carry the reply code in the `error` field so
  the basis of the classification stays inspectable.
- This ADR does not address accept-all domains, where servers return 250 to
  every RCPT TO as an anti-harvesting measure and a 250 is therefore not
  evidence the mailbox exists. That is tracked in ROADMAP.md under v0.55 and
  needs its own ADR.

## Alternatives considered
- **Implement ADR-0004 literally, all non-250 to UNKNOWN**: a smaller change
  requiring no new ADR, and defensible because no SMTP rejection is fully
  trustworthy. Rejected because it would make SMTP incapable of ever
  producing INVALID, discarding the strongest negative signal available for
  the sake of matching wording whose own stated reasoning pointed at 4xx.
- **Fix the code without recording a decision**: rejected. It would leave
  ADR-0004 permanently contradicting the code it documents, which is the
  condition that made this a roadmap item in the first place.
- **Treat 5xx as INVALID only when the enhanced status code is 5.1.1**: more
  precise, but enhanced status codes are optional and inconsistently
  emitted, so the added complexity buys little in practice.
