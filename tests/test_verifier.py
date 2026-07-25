"""
Unit tests for the email verifier.

Run with: pytest tests/test_verifier.py -v

Note: tests marked `smtp` require a live internet connection — either a
      DNS MX lookup, an SMTP handshake, or both.
      Run with: pytest -m "not smtp" to skip them offline.
"""

import pytest
from app.core import verifier
from app.core.verifier import verify, VStatus


def test_invalid_syntax_missing_at() -> None:
    """Address with no @ should fail syntax stage."""
    result = verify("notanemail", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.syntax_ok is False


def test_invalid_syntax_wrong_tld() -> None:
    """Non-.cl address should fail syntax stage."""
    result = verify("user@company.com", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.syntax_ok is False


def test_invalid_syntax_no_domain() -> None:
    """Address with no domain should fail syntax stage."""
    result = verify("user@.cl", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.syntax_ok is False


def test_valid_syntax_passes() -> None:
    """Well-formed .cl address should pass syntax stage."""
    result = verify("user@example.cl", smtp_enabled=False)
    assert result.syntax_ok is True


@pytest.mark.smtp
def test_no_smtp_returns_unknown() -> None:
    """With smtp_enabled=False and valid MX domain, status should be UNKNOWN."""
    result = verify("user@bcn.cl", smtp_enabled=False)
    assert result.syntax_ok is True
    assert result.mx_ok is True
    assert result.status == VStatus.UNKNOWN
    assert result.smtp_ok is None


@pytest.mark.smtp
def test_invalid_mx_domain() -> None:
    """Domain with no MX records should return INVALID."""
    result = verify("user@thisdoesnotexist123456.cl", smtp_enabled=False)
    assert result.status == VStatus.INVALID
    assert result.mx_ok is False


@pytest.mark.smtp
def test_error_message_populated_on_failure() -> None:
    """Failed verification should populate the error field."""
    result = verify("user@thisdoesnotexist123456.cl", smtp_enabled=False)
    assert result.error != ""


def test_mx_resolver_failure_is_unknown(monkeypatch) -> None:
    """
    A resolver that cannot answer is no information, not a verdict.

    This is the bug that reported 16 real @nunoa.cl addresses as INVALID:
    dnspython timed out against the configured nameservers, and the MX
    stage treated that identically to a nonexistent domain. See ADR-0009.
    """
    def _unavailable(domain):
        raise verifier.MXUnavailable("LifetimeTimeout: resolution expired")

    monkeypatch.setattr(verifier, "resolve_mx", _unavailable)
    result = verify("gbenavides@nunoa.cl", smtp_enabled=True)

    assert result.status == VStatus.UNKNOWN
    assert result.mx_ok is False
    assert "LifetimeTimeout" in result.error


def test_nonexistent_domain_is_still_invalid(monkeypatch) -> None:
    """A domain that definitively does not exist stays INVALID."""
    def _missing(domain):
        raise verifier.DomainNotFound(f"{domain} does not exist")

    monkeypatch.setattr(verifier, "resolve_mx", _missing)
    result = verify("user@thisdoesnotexist123456.cl", smtp_enabled=True)

    assert result.status == VStatus.INVALID
    assert result.mx_ok is False


def test_resolved_mx_reaches_the_smtp_stage(monkeypatch) -> None:
    """A successful lookup marks mx_ok and proceeds to SMTP."""
    monkeypatch.setattr(
        verifier, "resolve_mx", lambda domain: "aspmx.l.google.com"
    )
    monkeypatch.setattr(
        verifier.smtplib, "SMTP", type("_P", (_FakeSMTP,), {"rcpt_code": 250})
    )
    result = verify("gbenavides@nunoa.cl", smtp_enabled=True)

    assert result.mx_ok is True
    assert result.status == VStatus.VALID


class _FakeSMTP:
    """Stand-in for smtplib.SMTP returning a canned RCPT reply code."""

    rcpt_code = 250

    def __init__(self, *args, **kwargs) -> None:
        self._seen = 0

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def connect(self, host, port):
        return (220, b"ready")

    def helo(self, name=""):
        return (250, b"ok")

    def mail(self, sender):
        return (250, b"ok")

    def rcpt(self, recipient):
        # The first RCPT is the address under test. Anything after it is a
        # catch-all probe, and a selective server rejects those, so
        # rcpt_code keeps meaning "what this server says about the real
        # address" rather than "what it says about everything" (ADR-0016).
        self._seen += 1
        if self._seen == 1:
            return (self.rcpt_code, b"canned reply")
        return (550, b"no such user")


@pytest.fixture
def smtp_code(monkeypatch):
    """Force verify()'s SMTP stage to return a given RCPT reply code."""
    def _apply(code: int) -> None:
        monkeypatch.setattr(
            verifier, "resolve_mx", lambda domain: "mx.example.cl"
        )
        monkeypatch.setattr(
            verifier.smtplib,
            "SMTP",
            type("_Patched", (_FakeSMTP,), {"rcpt_code": code}),
        )
    return _apply


def test_smtp_250_is_valid(smtp_code) -> None:
    """A 250 acceptance is the only VALID outcome."""
    smtp_code(250)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.VALID
    assert result.smtp_ok is True


def test_smtp_550_is_invalid(smtp_code) -> None:
    """550 is a permanent failure: mailbox does not exist."""
    smtp_code(550)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.INVALID
    assert result.smtp_ok is False
    assert "550" in result.error


def test_smtp_450_greylisting_is_unknown(smtp_code) -> None:
    """450 is a transient deferral (greylisting), not a rejection."""
    smtp_code(450)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.UNKNOWN
    assert "450" in result.error


def test_smtp_421_rate_limit_is_unknown(smtp_code) -> None:
    """421 is a transient rate-limit, not a rejection."""
    smtp_code(421)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.UNKNOWN


def test_smtp_252_cannot_verify_is_unknown(smtp_code) -> None:
    """252 means the server states it cannot verify the address."""
    smtp_code(252)
    result = verify("user@example.cl", smtp_enabled=True)
    assert result.status == VStatus.UNKNOWN


@pytest.mark.smtp
def test_smtp_stage_runs_against_a_live_domain() -> None:
    """
    The pipeline reaches the SMTP stage against a real server and classifies
    the reply. What that reply is, is not this test's business.

    It used to assert that contacto@bcn.cl came back VALID or UNKNOWN, which
    passed until the mailbox was retired and the server began answering 550.
    The verifier was right and the test was wrong: it had outsourced its
    assertion to whether a stranger's mailbox still existed, so a correct
    INVALID read as a regression. What is ours to check is that syntax and MX
    ran, that the handshake completed rather than raising, and that whatever
    came back landed in one of the three buckets ADR-0009 defines.
    """
    result = verify("contacto@bcn.cl", smtp_enabled=True)
    assert result.syntax_ok is True
    assert result.mx_ok is True
    assert result.status in (VStatus.VALID, VStatus.UNKNOWN, VStatus.INVALID)
    # A definitive answer must say which one it was. UNKNOWN is the bucket
    # for "could not tell", so it is the only status allowed to carry no
    # reason (ADR-0004, ADR-0009).
    if result.status is not VStatus.UNKNOWN:
        assert result.error or result.smtp_ok, result

# ── Catch-all detection (ADR-0016)

class _ProbeSMTP:
    """
    Stand-in for smtplib.SMTP. `accepts` decides the reply to each RCPT:
    a callable taking the address and returning a code.
    """

    def __init__(self, accepts, timeout=None):
        self.accepts = accepts
        self.rcpts: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def connect(self, host, port):
        return 220, b'ok'

    def helo(self, name):
        return 250, b'ok'

    def mail(self, sender):
        return 250, b'ok'

    def rcpt(self, addr):
        self.rcpts.append(addr)
        return self.accepts(addr), b''


def _patch(monkeypatch, accepts):
    """Point verifier at a fake SMTP server and a resolvable MX."""
    holder = {}

    def _factory(timeout=None):
        holder['smtp'] = _ProbeSMTP(accepts, timeout)
        return holder['smtp']

    monkeypatch.setattr(verifier.smtplib, 'SMTP', _factory)
    monkeypatch.setattr(verifier, 'resolve_mx', lambda d: 'mx.example.cl')
    return holder


def test_catch_all_server_is_not_valid(monkeypatch) -> None:
    """A server that accepts everything has not confirmed the mailbox."""
    holder = _patch(monkeypatch, lambda addr: 250)

    result = verifier.verify('alguien@nunoa.cl')

    assert result.status is verifier.VStatus.CATCH_ALL
    assert 'accepts all recipients' in result.error


def test_selective_server_still_reports_valid(monkeypatch) -> None:
    """A server that rejects invented addresses confirms the real one."""
    holder = _patch(
        monkeypatch,
        lambda addr: 250 if addr == 'alguien@nunoa.cl' else 550,
    )

    result = verifier.verify('alguien@nunoa.cl')

    assert result.status is verifier.VStatus.VALID
    # The real address plus the probes that disproved catch-all.
    assert holder['smtp'].rcpts[0] == 'alguien@nunoa.cl'
    assert len(holder['smtp'].rcpts) > 1


def test_probes_are_high_entropy_and_plural(monkeypatch) -> None:
    """
    Guessable probes get rejected by servers that block abuse patterns,
    and one probe is not enough for deferred-rejection servers.
    """
    holder = _patch(monkeypatch, lambda addr: 250)

    verifier.verify('alguien@nunoa.cl')

    probes = holder['smtp'].rcpts[1:]
    assert len(probes) >= 2
    assert len(set(probes)) == len(probes)          # all distinct
    for probe in probes:
        local = probe.split('@')[0]
        assert len(local) >= 16
        assert probe.endswith('@nunoa.cl')


def test_one_rejected_probe_is_enough_to_clear_the_domain(monkeypatch) -> None:
    """Catch-all needs every probe accepted; one rejection settles it."""
    seen: list[str] = []

    def accepts(addr):
        seen.append(addr)
        if addr == 'alguien@nunoa.cl':
            return 250
        return 250 if len(seen) == 2 else 550

    _patch(monkeypatch, accepts)

    assert verifier.verify('alguien@nunoa.cl').status is verifier.VStatus.VALID


def test_catch_all_cache_asks_each_domain_once(monkeypatch) -> None:
    """Catch-all is a property of the server, not of the mailbox."""
    holder = _patch(monkeypatch, lambda addr: 250)
    cache: dict[str, bool] = {}

    for local in ('uno', 'dos', 'tres'):
        verifier.verify(f'{local}@nunoa.cl', catch_all_cache=cache)

    assert cache == {'nunoa.cl': True}
    # Last connection issued the real RCPT only: no repeat probing.
    assert holder['smtp'].rcpts == ['tres@nunoa.cl']


def test_probe_failure_does_not_invent_a_catch_all(monkeypatch) -> None:
    """Failing to prove a server accepts everything is not proof it does."""
    def accepts(addr):
        if addr == 'alguien@nunoa.cl':
            return 250
        raise verifier.smtplib.SMTPServerDisconnected('gone')

    _patch(monkeypatch, accepts)

    assert verifier.verify('alguien@nunoa.cl').status is verifier.VStatus.VALID


# ── 5xx is not automatically about the mailbox (RFC 3463 subclasses)

class _MsgSMTP(_ProbeSMTP):
    """Fake whose RCPT reply carries a real enhanced-status message."""

    def rcpt(self, addr):
        self.rcpts.append(addr)
        return self.accepts(addr)          # returns (code, msg)


def _patch_msg(monkeypatch, reply):
    holder = {}

    def _factory(timeout=None):
        holder['smtp'] = _MsgSMTP(lambda a: reply, timeout)
        return holder['smtp']

    monkeypatch.setattr(verifier.smtplib, 'SMTP', _factory)
    monkeypatch.setattr(verifier, 'resolve_mx', lambda d: 'mx.example.cl')
    return holder


def test_550_5_1_1_is_invalid(monkeypatch) -> None:
    """Bad destination mailbox: the address really is dead."""
    _patch_msg(monkeypatch, (550, b'5.1.1 User unknown'))
    assert verifier.verify('nadie@nunoa.cl').status is verifier.VStatus.INVALID


def test_550_5_7_1_is_unknown_not_invalid(monkeypatch) -> None:
    """
    5.7.1 is "you are not allowed", a permanent fact about the sender.
    Reporting it INVALID marks live addresses dead for everyone reading
    the CSV, which is the ADR-0009 error one stage later.
    """
    _patch_msg(monkeypatch, (550, b'5.7.1 Access denied, blocked'))
    result = verifier.verify('real@nunoa.cl')

    assert result.status is verifier.VStatus.UNKNOWN
    assert 'policy' in result.error


def test_550_5_4_1_is_unknown(monkeypatch) -> None:
    """5.4.x is routing: also not a statement about the mailbox."""
    _patch_msg(monkeypatch, (550, b'5.4.1 Recipient address rejected'))
    assert verifier.verify('a@nunoa.cl').status is verifier.VStatus.UNKNOWN


def test_550_without_enhanced_code_stays_invalid(monkeypatch) -> None:
    """Unchanged default: a bare 550 is still a permanent rejection."""
    _patch_msg(monkeypatch, (550, b'No such user here'))
    assert verifier.verify('a@nunoa.cl').status is verifier.VStatus.INVALID


def test_greylisting_is_flagged_for_retry(monkeypatch) -> None:
    """A greylisted address is live; it just answered later."""
    _patch_msg(monkeypatch, (451, b'4.7.1 Greylisting in action, come back'))
    result = verifier.verify('a@nunoa.cl')

    assert result.status is verifier.VStatus.UNKNOWN
    assert result.greylisted is True
    assert 'retrying' in result.error


def test_421_is_not_treated_as_greylisting(monkeypatch) -> None:
    """
    421 is load shedding or rate limiting. Retrying it promptly is how a
    temporary deferral becomes a block.
    """
    _patch_msg(monkeypatch, (421, b'4.7.0 Too many concurrent connections'))
    result = verifier.verify('a@nunoa.cl')

    assert result.status is verifier.VStatus.UNKNOWN
    assert result.greylisted is False


def test_probe_identity_names_no_one_elses_domain(monkeypatch) -> None:
    """
    RadarCL used to send HELO verify.cl and MAIL FROM check@verify.cl.
    verify.cl is registered to someone else, so every probe attributed
    itself to a stranger. Asserted on what goes over the wire, not on the
    source text, which still names the domain to explain the history.
    """
    monkeypatch.delenv('RADARCL_HELO', raising=False)
    sent: dict[str, str] = {}

    class _Recorder(_ProbeSMTP):
        def helo(self, name):
            sent['helo'] = name
            return 250, b'ok'

        def mail(self, sender):
            sent['mail'] = sender
            return 250, b'ok'

    monkeypatch.setattr(
        verifier.smtplib, 'SMTP',
        lambda timeout=None: _Recorder(lambda a: 250, timeout)
    )
    monkeypatch.setattr(verifier, 'resolve_mx', lambda d: 'mx.example.cl')

    verifier.verify('a@nunoa.cl')

    assert 'verify.cl' not in sent['helo']
    assert sent['mail'] == ''          # the null sender, not a borrowed one


def test_helo_override_is_honoured(monkeypatch) -> None:
    """Anyone with a real domain and a PTR record should use it."""
    monkeypatch.setenv('RADARCL_HELO', 'mail.ejemplo.cl')
    assert verifier._helo_name() == 'mail.ejemplo.cl'


def test_mailbox_full_is_not_invalid(monkeypatch) -> None:
    """
    X.2.2 is "mailbox full", which proves the mailbox exists. INVALID is
    plainly wrong; VALID would put a bouncing address in the CSV.
    """
    _patch_msg(monkeypatch, (552, b'5.2.2 Mailbox full'))
    result = verifier.verify('lleno@nunoa.cl')

    assert result.status is verifier.VStatus.UNKNOWN
    assert 'exists' in result.error


def test_mailbox_disabled_is_invalid(monkeypatch) -> None:
    """X.2.1 is a disabled mailbox: a hard bounce, suppress it."""
    _patch_msg(monkeypatch, (550, b'5.2.1 Mailbox disabled'))
    assert verifier.verify('a@nunoa.cl').status is verifier.VStatus.INVALID


def test_protocol_error_is_not_about_the_address(monkeypatch) -> None:
    """X.5.x is about this conversation, not about the recipient."""
    _patch_msg(monkeypatch, (500, b'5.5.2 Syntax error, command unrecognized'))
    assert verifier.verify('a@nunoa.cl').status is verifier.VStatus.UNKNOWN


def test_mail_system_error_is_not_about_the_address(monkeypatch) -> None:
    """X.3.x is their mail system having a problem."""
    _patch_msg(monkeypatch, (554, b'5.3.0 Other mail system problem'))
    assert verifier.verify('a@nunoa.cl').status is verifier.VStatus.UNKNOWN
