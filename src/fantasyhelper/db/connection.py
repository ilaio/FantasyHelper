"""Path and connection for the local SQLite file."""

import sqlite3
from pathlib import Path


def project_root() -> Path:
    """Repo root. This file is src/fantasyhelper/db/connection.py."""
    return Path(__file__).resolve().parents[3]


def database_path() -> Path:
    return project_root() / "data" / "fantasyhelper.sqlite3"


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
