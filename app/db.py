"""app/db.py — SQLite connection and schema initialisation."""
import sqlite3
from contextlib import contextmanager
from typing import Generator

from app.config import DB_PATH

# DDL -------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS leads (
  id                    INTEGER PRIMARY KEY,
  email                 TEXT    UNIQUE NOT NULL,
  last_name             TEXT,
  first_name            TEXT,
  rep                   TEXT    NOT NULL,
  chaleur               INTEGER NOT NULL CHECK (chaleur BETWEEN 0 AND 10),
  arrived_on            DATE    NOT NULL,
  call_count            INTEGER NOT NULL DEFAULT 0,
  status                TEXT    NOT NULL DEFAULT 'new',
  last_contact_date     DATE,
  next_followup_date    DATE,
  next_followup_time    TEXT,
  last_outcome          TEXT,
  consecutive_no_answer INTEGER NOT NULL DEFAULT 0,
  funding_status        TEXT    NOT NULL DEFAULT 'unknown',
  lost_reason           TEXT,
  notes                 TEXT    DEFAULT '',
  created_at            TEXT,
  updated_at            TEXT
);

CREATE INDEX IF NOT EXISTS idx_leads_rep_next  ON leads(rep, next_followup_date);
CREATE INDEX IF NOT EXISTS idx_leads_status    ON leads(status);

CREATE TABLE IF NOT EXISTS interactions (
  id       INTEGER PRIMARY KEY,
  lead_id  INTEGER NOT NULL REFERENCES leads(id),
  at       TEXT    NOT NULL,
  rep      TEXT    NOT NULL,
  channel  TEXT    NOT NULL DEFAULT 'call',
  outcome  TEXT    NOT NULL,
  note     TEXT    DEFAULT ''
);
"""


def init_db(db_path: str = DB_PATH) -> None:
    """Create tables if they don't exist."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


@contextmanager
def get_conn(db_path: str = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Yield a connection with row_factory set to Row."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
