# 0016 - A catch-all domain is not a valid address

## Status
Accepted

## Date
2026-07-25

## Deciders
Felipe Carvajal Brown

## Context
`verifier.py` treated an SMTP `250` reply to `RCPT TO` as proof the mailbox
exists, and reported the address VALID. That is true of a server that
distinguishes real recipients from invented ones. It is false of a catch-all
server, which accepts every recipient by design, as an anti-harvesting measure
and to avoid leaking its user list. Yahoo, AOL, mail.com and hardened Exchange
estates all behave this way.

The consequence was specific and bad: those addresses landed in the CSV, which
[ADR-0010](0010-export-contents-differ-by-format.md) defines as the mailable
deliverable. Every other verification outcome RadarCL gets wrong is either
recoverable (an UNKNOWN worth retrying) or invisible. This one put addresses
that had never been confirmed into the one file whose purpose is addresses you
can send to, and catch-all addresses carry substantially higher bounce rates
than verified ones.

This is the same error [ADR-0009](0009-mx-resolution-failure-is-unknown.md)
corrected on the DNS side, in the opposite direction. There, a resolver that
could not answer was being read as proof of absence. Here, a server that
answers yes to everything is being read as proof of presence. Both mistake the
absence of information for information.

Surveyed 2026-07-25 rather than assumed:

- The detection method is a second `RCPT TO` for a local part that cannot
  exist. If the server accepts an address nobody could have registered, it
  accepts everything.
- **The probe must be high entropy.** Some servers reject local parts matching
  known abuse patterns while accepting everything else, so a guessable probe
  reports "not catch-all" on a server that is one.
- **One probe is not enough.** Servers with deferred rejection can accept a
  single unlucky address, and multiple random probes are materially more
  reliable than one.
- The technique has real limits. Greylisting servers answer `4xx` on first
  contact regardless. Microsoft 365's default accept-all behaviour accepts at
  SMTP and rejects later at the application layer, so the probe sees `250` and
  the bounce arrives anyway.
- Commercial verification APIs do not solve this either: every provider sits at
  70-85% accuracy on catch-all domains, which is part of why
  [ADR-0015](0015-no-third-party-verification-api.md) declined to buy one.

## Decision
**`VStatus.CATCH_ALL` is a fourth verification outcome**, alongside VALID,
UNKNOWN and INVALID. A `250` from a server that also accepts invented addresses
produces CATCH_ALL, not VALID.

It is deliberately not folded into UNKNOWN. "The server would not tell us" and
"the server says yes to everything" are different facts with different
remedies: the first is worth retrying from another network, the second will
give the same answer forever.

It is equally not INVALID. The address may well exist; nothing was disproved.
Calling it invalid would repeat the error ADR-0009 fixed.

**Detection uses two probes with 20 hex characters of entropy each**, issued
over the connection already open for the real address, so it costs extra `RCPT`
commands rather than an extra session. **Every probe must be accepted** before
a domain is called catch-all: one rejection proves the server distinguishes
real mailboxes from invented ones, which is the entire question. Any error
during probing returns "not catch-all", because failing to prove a server
accepts everything is not evidence that it does.

**The verdict is cached per domain for the run.** Catch-all is a property of
the mail server, not of the mailbox, so a scan finding 23 addresses at
`nunoa.cl` asks its server once. `verify()` takes an optional
`catch_all_cache`, and `pipeline.verify_all` owns one for the whole run rather
than keeping module-level state. Passing nothing still works and probes every
time, which is correct but wasteful and, repeated against one server, looks
exactly like the harvesting the servers are defending against.

**CATCH_ALL is excluded from the CSV and present in JSON and HTML.** This needs
no new principle: ADR-0010 already makes the CSV the mailable list and the
other two the run record. The HTML report labels it "Acepta todo" and explains
in Spanish what that means, because a user who sees an address vanish from
their CSV deserves to know it was the server's answer that was worthless, not
the address.

## Consequences
- Addresses at catch-all domains stop appearing in the CSV. Some of them are
  real, and this is a deliberate loss: the tool cannot tell which, and the CSV
  is the file whose value depends on not guessing. They remain in the JSON and
  HTML with a status explaining why.
- **Verification issues more SMTP commands.** Two extra `RCPT` per domain, not
  per address, on domains whose first address returns `250`. On a `nunoa.cl`
  scan that is two extra commands across 23 addresses.
- Any consumer switching on the status string must handle `catch_all`. The
  exporters and `summarize()` do; an outside caller of `app/core/` as a library
  may not, and a status it does not recognise now appears.
- `summarize()` reports four buckets rather than three, all present at zero.
- The existing SMTP fake in `tests/test_verifier.py` returned the same reply to
  every recipient, which is the definition of a catch-all server, so the tests
  asserting `250` means VALID were encoding the behaviour this ADR corrects.
  The fake now accepts the address under test and rejects probes, modelling a
  selective server, and `rcpt_code` keeps meaning "what this server says about
  the real address".
- Greylisting and Microsoft 365's delayed rejection are not solved. A `4xx`
  still lands in UNKNOWN, and an M365 estate that accepts at SMTP and bounces
  later will still be reported CATCH_ALL rather than INVALID. Recorded because
  the feature will be blamed for both.

## Alternatives considered
- **Fold it into UNKNOWN with a distinct error string.** The smallest change,
  and nothing downstream would need updating. Rejected because it discards the
  distinction between a server that could not answer and one that answers yes
  to everything, and that distinction is the only actionable part: one is worth
  a retry, the other never will be.
- **Keep CATCH_ALL in the CSV, labelled.** A larger usable list, and on many
  catch-all domains the address is genuine. Rejected because the CSV's entire
  purpose is addresses that can be mailed, and these are precisely the ones
  that bounce.
- **A single probe.** Half the SMTP traffic. Rejected on the measured behaviour
  of deferred-rejection servers, where one accepted probe is not evidence, and
  because the failure would be silent: the feature would look correct while
  being wrong on exactly the hardened estates that motivate it.
- **Probe per address rather than per domain.** Simpler, no cache to reason
  about. Rejected because it asks one server the same question 23 times in a
  scan, which is wasteful and is itself the pattern that gets an address
  blocked.
- **Measure `.cl` catch-all prevalence before building.** Consistent with how
  v0.40 and v0.50 were settled, and the 12-15% figure in the literature is
  about US B2B domains rather than Chile. Weighed and not taken: unlike a
  discovery stage, whose value is unknown until measured, this one corrects a
  known wrong answer, and the measurement would refine how often it fires
  rather than whether it should exist. Worth running later to size the effect.
