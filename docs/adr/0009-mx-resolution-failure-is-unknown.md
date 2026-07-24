# 0009 - MX resolution failure is UNKNOWN, with fallback transports

## Status
Accepted - supersedes [0007](0007-smtp-response-classification.md)

## Date
2026-07-24

## Deciders
Felipe Carvajal Brown

## Context
A real crawl of `nunoa.cl` found 16 published municipal addresses and
reported every one of them INVALID. They were all genuine.

Investigation established the following, in order:

- `nunoa.cl` publishes valid MX records pointing at Google Workspace
  (`ASPMX.L.GOOGLE.COM`), confirmed over DNS-over-HTTPS.
- An SMTP `RCPT TO` probe against that host returns `250 OK` for
  `gbenavides@nunoa.cl` and `550 5.1.1 ... does not exist` for a
  deliberately fabricated address, so the mail server answers verification
  probes honestly and [ADR-0007](0007-smtp-response-classification.md)'s
  reply-code classification was behaving correctly.
- Repeating the probe for ten of the addresses, each on a fresh connection
  exactly as `verify()` does, returned `250 OK` for all ten. No rate
  limiting was involved.
- `verify('gbenavides@nunoa.cl')` nevertheless returned INVALID with
  `mx_ok=False` and the error `No MX record: The resolution lifetime
  expired after 5.008 seconds ... The DNS operation timed out`.

The cause is in the MX stage of `app/core/verifier.py`, which wrapped the
lookup in a bare `except Exception` and mapped everything it caught to
INVALID. That conflates two unrelated outcomes: `NXDOMAIN`, where the domain
genuinely does not exist, and a resolver timeout, where nothing at all was
learned.

dnspython queries the configured nameservers directly over UDP port 53.
Where those servers are unreachable or the port is filtered, it times out
even though ordinary HTTPS traffic is unaffected - which is why the crawler
fetched every page successfully and the verifier then declared every address
on those pages dead.

This is the same defect [ADR-0007](0007-smtp-response-classification.md)
corrected one stage later in the pipeline. That ADR restated the rule that
"a hard syntax or MX failure sets INVALID" without distinguishing kinds of
MX failure, so it carried the flaw forward. The underlying principle from
[ADR-0004](0004-verification-staging-unknown-not-invalid.md) - that an
indeterminate result is UNKNOWN and never INVALID - was correct all along
and simply was not applied to DNS.

## Decision
Two changes, recorded together because the second is what makes the first
useful rather than merely honest.

**Classification.** MX resolution outcomes are separated by kind, in a new
`app/core/dns_lookup.py` that raises a distinct exception for each:

| Outcome | Exception | Status |
|---|---|---|
| `NXDOMAIN` | `DomainNotFound` | INVALID |
| No MX and no A record | `DomainNotFound` | INVALID |
| No MX, A record present | resolved via implicit MX | continues |
| Timeout, unreachable nameservers, any transport failure | `MXUnavailable` | UNKNOWN |

The implicit-MX case follows RFC 5321 section 5.1: where a domain publishes
no MX record, its address record is the mail exchanger. Previously such a
domain was reported INVALID.

**Fallback transports.** `resolve_mx()` tries the system resolver, then the
public nameservers `8.8.8.8` and `1.1.1.1`, then DNS-over-HTTPS via
`https://dns.google/resolve`, stopping at the first that answers. A
`DomainNotFound` short-circuits the chain, since no second resolver can
rescue a domain that does not exist. The DoH leg exists specifically because
it works where UDP/53 is filtered, which is the failure that produced this
ADR.

Everything else from ADR-0007 is retained unchanged: the staging order, the
SMTP reply-code table (250 valid, 5xx invalid, 4xx and 252 unknown), and
UNKNOWN as a first-class outcome.

## Consequences
- Real addresses behind an unresponsive resolver are no longer reported as
  invalid. Verified: the four-case check - two real addresses, one
  fabricated address at a real domain, one nonexistent domain - now returns
  VALID, VALID, INVALID and INVALID respectively on a machine where UDP DNS
  does not work at all.
- Verification now functions on networks whose configured nameservers are
  broken or filtered, rather than silently producing wrong verdicts.
- Verification makes outbound HTTPS requests to `dns.google` when both DNS
  paths fail. That is a third-party dependency and a privacy consideration:
  the queried domain is disclosed to Google. It only happens as a last
  resort, and the crawler already contacts external services, but it is a
  new egress path worth stating plainly.
- A failing lookup is now slower in the worst case, up to three transports
  at a 5-second budget each, because the code keeps trying instead of
  concluding early from one failure.
- `app/core/` gains a module, and `verifier.py` no longer imports
  `dns.resolver` directly. Tests can substitute individual transports.

## Alternatives considered
- **Classification fix alone, no fallback**: smaller and introduces no new
  network behaviour. Rejected as insufficient. It converts sixteen wrong
  INVALIDs into sixteen useless UNKNOWNs; the tool would be honest and still
  unable to verify anything on the affected machine.
- **Fallback alone, no classification change**: the visible symptom
  disappears because lookups start succeeding. Rejected because it leaves
  the misclassification latent, so any resolver failure the fallback cannot
  cover would still report real addresses as invalid.
- **Treat every MX failure as UNKNOWN, including NXDOMAIN**: simplest rule
  and impossible to get wrong in the false-negative direction. Rejected
  because a nonexistent domain is one of the few genuinely definitive
  signals available, and discarding it would make syntax the only source of
  INVALID short of an SMTP 5xx.
- **Ship a bundled resolver configuration instead of DoH**: avoids the
  third-party HTTPS dependency. Rejected because public nameservers are
  already the second leg, and if UDP/53 is filtered they fail for the same
  reason the system resolver did. HTTPS is the only transport that survives
  that condition.
