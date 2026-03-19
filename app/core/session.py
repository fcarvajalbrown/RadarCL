"""
SQLite-backed session store.

Persists email discoveries and verification results.
Keeps last 10 sessions; older ones pruned automatically.
DB location: ~/.radarcl/sessions.db
"""

import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path.home() / '.radarcl' / 'sessions.db'


def _get_conn() -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure schema exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            target_domain TEXT,
            seed_urls TEXT,
            total_found INTEGER DEFAULT 0,
            total_valid INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            source_url TEXT,
            status TEXT DEFAULT 'unknown',
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)
    conn.commit()
    return conn


def new_session(target_domain: str, seed_urls: list[str]) -> int:
    """
    Create a new session record.

    Parameters
    ----------
    target_domain : str
        The target email domain (e.g. @bhp.cl).
    seed_urls : list[str]
        Seed URLs used for this session.

    Returns
    -------
    int
        The new session ID.
    """
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO sessions (created_at, target_domain, seed_urls) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), target_domain, ','.join(seed_urls))
    )
    conn.commit()
    session_id = cur.lastrowid
    _prune_old_sessions(conn)
    conn.close()
    return session_id


def save_email(
    session_id: int,
    email: str,
    source_url: str,
    status: str = 'unknown',
) -> None:
    """
    Insert a single email record into the store.

    Parameters
    ----------
    session_id : int
    email : str
    source_url : str
    status : str
        One of: 'unknown', 'valid', 'invalid'.
    """
    conn = _get_conn()
    conn.execute(
        "INSERT INTO emails (session_id, email, source_url, status) VALUES (?, ?, ?, ?)",
        (session_id, email, source_url, status)
    )
    conn.commit()
    conn.close()


def load_session(session_id: int) -> list[dict]:
    """
    Load all emails for a given session.

    Parameters
    ----------
    session_id : int

    Returns
    -------
    list[dict]
        Each dict has keys: email, source_url, status.
    """
    conn = _get_conn()
    cur = conn.execute(
        "SELECT email, source_url, status FROM emails WHERE session_id = ?",
        (session_id,)
    )
    rows = [{'email': r[0], 'source': r[1], 'status': r[2]} for r in cur.fetchall()]
    conn.close()
    return rows


def list_sessions() -> list[dict]:
    """
    Return the last 10 sessions in reverse chronological order.

    Returns
    -------
    list[dict]
        Each dict has keys: id, created_at, target_domain, total_found, total_valid.
    """
    conn = _get_conn()
    cur = conn.execute(
        "SELECT id, created_at, target_domain, total_found, total_valid "
        "FROM sessions ORDER BY id DESC LIMIT 10"
    )
    rows = [
        {
            'id': r[0],
            'created_at': r[1],
            'target_domain': r[2],
            'total_found': r[3],
            'total_valid': r[4],
        }
        for r in cur.fetchall()
    ]
    conn.close()
    return rows


def _prune_old_sessions(conn: sqlite3.Connection, keep: int = 10) -> None:
    """Delete sessions beyond the most recent `keep` records."""
    conn.execute("""
        DELETE FROM sessions WHERE id NOT IN (
            SELECT id FROM sessions ORDER BY id DESC LIMIT ?
        )
    """, (keep,))
    conn.commit()