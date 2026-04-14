import os
import sqlite3
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent.parent.parent.parent / "data" / "errors.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS errors (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),

    stack            TEXT    NOT NULL,
    module           TEXT,
    error_type       TEXT,
    severity         TEXT    NOT NULL DEFAULT 'medium',

    symptom          TEXT    NOT NULL,
    root_cause       TEXT    NOT NULL,
    fix              TEXT    NOT NULL,
    prevention       TEXT,
    tags             TEXT,

    file_path        TEXT,
    test_added       TEXT,

    times_referenced INTEGER NOT NULL DEFAULT 0,
    was_effective    INTEGER NOT NULL DEFAULT 1
);

CREATE VIRTUAL TABLE IF NOT EXISTS errors_fts USING fts5(
    symptom,
    root_cause,
    fix,
    tags,
    content='errors',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS errors_after_insert AFTER INSERT ON errors BEGIN
    INSERT INTO errors_fts(rowid, symptom, root_cause, fix, tags)
    VALUES (new.id, new.symptom, new.root_cause, new.fix, COALESCE(new.tags, ''));
END;

CREATE TRIGGER IF NOT EXISTS errors_after_update AFTER UPDATE ON errors BEGIN
    INSERT INTO errors_fts(errors_fts, rowid, symptom, root_cause, fix, tags)
    VALUES ('delete', old.id, old.symptom, old.root_cause, old.fix, COALESCE(old.tags, ''));
    INSERT INTO errors_fts(rowid, symptom, root_cause, fix, tags)
    VALUES (new.id, new.symptom, new.root_cause, new.fix, COALESCE(new.tags, ''));
END;

CREATE TABLE IF NOT EXISTS patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stack           TEXT    NOT NULL,
    pattern         TEXT    NOT NULL,
    example         TEXT,
    fix_example     TEXT,
    source_error_id INTEGER REFERENCES errors(id)
);
"""


def get_db_path() -> Path:
    env_path = os.environ.get("DB_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_DB


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_SCHEMA_SQL)
