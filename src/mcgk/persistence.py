"""
SQLite persistence for MCGK registry and observability logs.

- Passports survive restarts. Health state is ephemeral.
- Request logs survive restarts.
"""

from __future__ import annotations

import json
import sqlite3

from .config import DB_PATH
from .models import EndpointSpec, InternalRecord, RequestLog


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contours (
            name        TEXT PRIMARY KEY,
            address     TEXT NOT NULL,
            description TEXT NOT NULL,
            endpoints   TEXT NOT NULL,
            registered_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   REAL NOT NULL,
            source      TEXT,
            target      TEXT NOT NULL,
            target_path TEXT NOT NULL,
            method      TEXT NOT NULL,
            status_code INTEGER,
            error       TEXT,
            duration_ms REAL
        )
    """)
    conn.commit()
    return conn


def save_contour(record: InternalRecord) -> None:
    """Insert or replace a contour record."""
    conn = _connect()
    conn.execute(
        """INSERT OR REPLACE INTO contours (name, address, description, endpoints, registered_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            record.name,
            record.address,
            record.description,
            json.dumps([ep.model_dump() for ep in record.endpoints]),
            record.registered_at,
        ),
    )
    conn.commit()
    conn.close()


def load_all_contours() -> dict[str, InternalRecord]:
    """Load all contours from DB. Health is set to False — must be re-confirmed."""
    conn = _connect()
    rows = conn.execute(
        "SELECT name, address, description, endpoints, registered_at FROM contours"
    ).fetchall()
    conn.close()

    result: dict[str, InternalRecord] = {}
    for name, address, description, endpoints_json, registered_at in rows:
        endpoints = [EndpointSpec(**ep) for ep in json.loads(endpoints_json)]
        result[name] = InternalRecord(
            name=name,
            address=address,
            description=description,
            endpoints=endpoints,
            healthy=False,
            registered_at=registered_at,
            last_health_check=None,
        )
    return result


def delete_contour(name: str) -> None:
    """Remove a contour from persistence."""
    conn = _connect()
    conn.execute("DELETE FROM contours WHERE name = ?", (name,))
    conn.commit()
    conn.close()


# ── Request log persistence ──────────────────────────────────────────

def save_request_log(log: RequestLog) -> None:
    """Persist a single request log entry."""
    conn = _connect()
    conn.execute(
        """INSERT INTO request_logs (timestamp, source, target, target_path, method, status_code, error, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (log.timestamp, log.source, log.target, log.target_path,
         log.method, log.status_code, log.error, log.duration_ms),
    )
    conn.commit()
    conn.close()


def load_request_logs(target: str | None = None, limit: int = 500) -> list[dict]:
    """Load request logs from DB, newest first. Optionally filter by target."""
    conn = _connect()
    if target:
        rows = conn.execute(
            "SELECT timestamp, source, target, target_path, method, status_code, error, duration_ms "
            "FROM request_logs WHERE target = ? ORDER BY id DESC LIMIT ?",
            (target, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT timestamp, source, target, target_path, method, status_code, error, duration_ms "
            "FROM request_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    cols = ("timestamp", "source", "target", "target_path", "method", "status_code", "error", "duration_ms")
    return [dict(zip(cols, row)) for row in rows]
