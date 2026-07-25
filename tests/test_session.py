"""
Unit tests for the SQLite session store.

Offline: DB_PATH is redirected to a tmp file per test, so nothing touches
~/.radarcl/sessions.db. Run with:
    pytest tests/test_session.py -v
"""

import pytest

from app.core import session


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the module at a throwaway database."""
    monkeypatch.setattr(session, 'DB_PATH', tmp_path / 'sessions.db')
    return session


def test_totals_start_at_zero_and_are_written(store) -> None:
    """
    A finished session records what it found.

    `total_found` and `total_valid` existed from the first schema and
    nothing ever wrote them, so every session read back claimed to have
    found nothing. This asserts the write, not the schema default.
    """
    session_id = store.new_session('nunoa.cl', ['https://nunoa.cl'])

    assert store.list_sessions()[0]['total_found'] == 0

    store.update_session_totals(session_id, 23, 9)

    row = store.list_sessions()[0]
    assert row['total_found'] == 23
    assert row['total_valid'] == 9


def test_totals_are_scoped_to_their_own_session(store) -> None:
    """Writing one session's totals must not touch another's."""
    first = store.new_session('nunoa.cl', [])
    second = store.new_session('providencia.cl', [])

    store.update_session_totals(first, 5, 2)

    rows = {r['id']: r for r in store.list_sessions()}
    assert (rows[first]['total_found'], rows[first]['total_valid']) == (5, 2)
    assert (rows[second]['total_found'], rows[second]['total_valid']) == (0, 0)


def test_status_survives_the_two_phase_write(store) -> None:
    """
    Discovery saves without a status; verification fills it in.

    The GUI saves an address the moment it is found, when nothing is known
    about it yet, and updates it after verification. That is deliberate,
    not a dropped argument, and this pins the sequence so a later reader
    does not "fix" it.
    """
    session_id = store.new_session('nunoa.cl', [])
    store.save_email(session_id, 'ana@nunoa.cl', 'https://nunoa.cl/contacto')

    assert store.load_session(session_id)[0]['status'] == 'unknown'

    store.update_email_status(session_id, 'ana@nunoa.cl', 'valid')

    assert store.load_session(session_id)[0]['status'] == 'valid'
