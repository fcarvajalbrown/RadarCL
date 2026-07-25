# 0017 - A reply is evidence only about its subject

## Status
Accepted. Narrows [0009](0009-mx-resolution-failure-is-unknown.md).

## Date
2026-07-25

## Deciders
Felipe Carvajal Brown

## Context
[ADR-0009](0009-mx-resolution-failure-is-unknown.md) fixed one instance of a
mistake: a DNS resolver that could not answer was being read as proof the
domain had no mail exchanger, so sixteen live `@nunoa.cl` addresses were
reported INVALID. The fix was correct and narrow. The mistake was not.

Researched on 2026-07-25 across eighty searches and then checked against the
code, the same confusion turned out to be sitting in five more places, all of
them shipping. In each, RadarCL read a fact about *something other than the
address* as a fact about the address.

**Every 5xx was INVALID.** RFC 3463's middle digit is the *subject*: which part
of the mail system a status concerns.

| Subject | Meaning | Speaks about |
|---|---|---|
| 1 | Addressing | the address |
| 2 | Mailbox | the mailbox |
| 3 | Mail system | the far end's system |
| 4 | Network | the route |
| 5 | Protocol | this conversation |
| 6 | Content | the message |
| 7 | Security | policy, authentication |

Only subjects 1 and 2 are about the recipient. A `550 5.7.1` means the server
refuses *this sender*: a permanent fact about RadarCL. Reporting it INVALID
writes "this address is dead" into the CSV on the strength of RadarCL being
blocked, and everyone downstream inherits the error. Microsoft's `5.7.606-649`
is explicitly "banned sending IP"; `554` is generic and carries its real
meaning in the enhanced code.

**`X.2.2` is mailbox full.** That is proof the mailbox *exists*. It was
INVALID, which is the strongest possible wrong answer.

**A null MX was UNKNOWN.** [RFC 7505](https://www.rfc-editor.org/rfc/rfc7505)
lets a domain publish a single MX of `.` to say it accepts no mail.
`resolve_mx` returned that `.` as a hostname, the SMTP stage failed to connect
to it, and the result was UNKNOWN: an explicit "no" recorded as "we could not
tell".

**Greylisting was indistinguishable from congestion.** A greylisting server
answers 4xx on first contact and accepts a later retry from the same IP. Those
addresses are live and were being filed with genuine unknowns, with nothing
marking them as worth asking again.

**And RadarCL was not itself.** Every probe sent `HELO verify.cl` and
`MAIL FROM:<check@verify.cl>`. `verify.cl` is a registered domain, with an A
record at `54.88.168.60` and AWS nameservers, belonging to someone else. Every
probe this tool has ever sent attributed itself to a stranger, so any
complaint, bounce or blocklisting RadarCL earned landed on them. It is the same
error pointed outward: a claim made about a party the evidence did not concern.

## Decision
**A reply is evidence only about its subject.** That is the general rule
ADR-0009 was one case of, and it is now stated once rather than rediscovered
per stage.

**5xx replies are classified by RFC 3463 subject, not by the leading digit.**
Subjects 1 and 2 are about the recipient and stay INVALID. Subjects 3 through 7
become UNKNOWN, with an error naming why. A 5xx carrying no enhanced code at
all is unchanged and stays INVALID, since guessing from prose would trade a
known rule for a worse one.

**`X.2.2` is UNKNOWN**, not INVALID and not VALID. The mailbox exists and will
not take mail today. VALID would put a bouncing address in the CSV, which is
the one file whose value depends on not guessing.

**A null MX is INVALID.** It is a definitive answer, so it belongs with
`DomainNotFound` rather than with the timeouts ADR-0009 put in UNKNOWN.

**Greylisted replies are flagged.** They stay UNKNOWN, because nothing was
learned yet, but they carry a marker and a reason, so a second pass can ask
again. `421` is deliberately excluded: it is load shedding or rate limiting,
and retrying it promptly is how a deferral becomes a block.

**RadarCL announces itself as itself.** The HELO name is the machine's own
FQDN, overridable with `RADARCL_HELO` for anyone running from a host with a
real domain and a matching PTR record. The envelope sender is the null sender,
the convention for probes that will never send and what Postfix's own address
verification uses, falling back to `postmaster@` for servers that reject it.

**This ships as a correction, stated plainly, not as a feature.** There is no
defensible version of continuing to name a domain the project does not own, so
the change needs no migration path and gets none. Acceptance was checked live
against `ASPMX.L.GOOGLE.COM`: the honest identity gets the same 250 the
borrowed one did.

**Narrows ADR-0009 rather than superseding it**, following ADR-0013 and
ADR-0014. ADR-0009's MX reasoning, its fallback transports and its measurements
all still govern shipping code. What changes is that its principle now covers
the SMTP stage too, and its statement that a 5xx is INVALID is qualified.

## Consequences
- **Fewer INVALIDs, and the ones remaining mean more.** Any address whose
  server refuses RadarCL over policy moves from INVALID to UNKNOWN. Users
  comparing runs across this version will see counts shift with no change in
  the addresses themselves.
- **Every probe now carries this host's name instead of a stranger's.** On a
  machine with no fully qualified name that is `localhost.localdomain`, which
  some servers score down. That is the honest cost, the knob exists, and it was
  measured as making no difference on the one live server tested. A wider
  measurement of acceptance rates by HELO name has not been done.
- Two more `VerificationResult` fields' worth of meaning: `greylisted`, and an
  `error` that now explains *why* something is UNKNOWN rather than only quoting
  a code.
- **The greylist flag is surfaced but not acted on.** Nothing retries
  automatically. A second pass over the flagged addresses is the user's to run,
  through the `verify` subcommand, and an automatic retry with a real delay is
  not designed here.
- Deliberately not addressed: Yahoo and AOL answer 250 or 252 to everything, and
  Microsoft 365 estates can accept at SMTP and bounce later. The first is
  handled as catch-all by ADR-0016. The second is not detectable from a
  handshake at all, and this ADR does not pretend otherwise.
- Measured on 20 real `.cl` domains while testing this: 17% of reachable ones
  are catch-all, and Microsoft 365 carries 12 of 20, every one of them
  answering selectively. The literature's warning that M365 always looks
  catch-all did not hold for Chilean institutions.

## Alternatives considered
- **Two ADRs, splitting classification from probe identity.** The identity fix
  is about how RadarCL presents itself rather than how it reads replies.
  Rejected because all six defects are one mistake in six places, and splitting
  the record would hide the thing most worth recording: that fixing ADR-0009's
  instance did not fix its cause.
- **Supersede ADR-0009.** Rejected because its DNS reasoning and measurements
  are untouched and would have to be re-derived to keep the record complete,
  which is the trade ADR-0013 and ADR-0014 already declined.
- **Guess at 5xx meaning from the reply text when no enhanced code is
  present.** Several vendors do exactly this, matching phrases like "user
  unknown". Rejected for now: it replaces a specified rule with an unspecified
  one, and the current default is at least predictable. Worth revisiting with a
  corpus of real replies rather than a guess about them.
- **Treat `X.2.2` as VALID**, on the grounds that the mailbox demonstrably
  exists. Rejected because the CSV is the mailable list and that address
  bounces today.
- **Require `RADARCL_HELO` before any SMTP probe runs.** The most correct
  position: never speak to a mail server without naming a host you control.
  Rejected because the fallback measured fine and the requirement would break
  every existing workflow to fix a problem the fallback does not have.
- **Retry greylisted addresses automatically inside a run.** Rejected as
  undesigned rather than unwanted: greylisting windows are minutes, a scan's
  own duration is not a reliable substitute for waiting, and a retry pass that
  fires too early teaches the user the flag is worthless.
