# 0004 - Staged verification with UNKNOWN as a first-class outcome

## Status
Superseded by [0007](0007-smtp-response-classification.md)

## Date
2026-07-23 (retroactive - decision predates this record)

## Deciders
Felipe Carvajal Brown

## Context
Verifying an email address for real requires increasingly expensive and
increasingly unreliable checks: syntax is free and certain, an MX lookup is
cheap and fairly reliable, and an SMTP `RCPT TO` handshake is the closest
thing to ground truth but many mail servers greylist, rate-limit, or flatly
refuse verification probes regardless of whether the address is real.
Treating a blocked/ambiguous SMTP response as simply "invalid" would produce
false negatives on real addresses.

## Decision
`verify()` (`app/core/verifier.py`) runs stages in order - syntax regex, DNS
MX lookup, SMTP handshake (`smtplib`, no mail actually sent), then an
optional API stage (currently a placeholder) - and stops at the first
definitive failure. Only a hard syntax or MX failure sets `VStatus.INVALID`.
An SMTP exception, timeout, or non-250 response that doesn't come from a
prior definitive stage failure results in `VStatus.UNKNOWN`, not `INVALID`.
The GUI's "Quick" vs "Deep" verification setting simply toggles whether the
SMTP stage runs at all (`smtp_enabled`).

## Consequences
- Users see three honest buckets - valid, invalid, unknown - instead of a
  binary that would misclassify addresses behind defensive mail servers as
  invalid.
- `VerifierWorker` and `app/core/exporter.py` both key off `status == 'valid'`
  for the auto-exported CSV, so UNKNOWN addresses are surfaced in the results
  table but excluded from the auto-export - a real user-facing consequence of
  this staging choice.
- "Quick" mode (no SMTP) can never produce `VALID` - only `UNKNOWN` or
  `INVALID` from syntax/MX - which is expected but worth remembering when
  reading exported results.

## Alternatives considered
- **Binary valid/invalid, no UNKNOWN**: simpler status model, but would force
  every blocked/ambiguous SMTP response into "invalid," discarding
  real addresses whose mail servers happen to be defensive.
- **Retry SMTP with backoff before giving up**: could reduce UNKNOWN rate,
  but adds significant runtime per email at the scale RadarCL verifies
  (dozens to hundreds per session) for uncertain benefit against servers that
  are deliberately blocking probes rather than transiently failing.
