"""SQLite operations for CodeGraph."""
from __future__ import annotations
import json, sqlite3, time

def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY, code TEXT NOT NULL, language TEXT NOT NULL,
            kind TEXT NOT NULL, status TEXT DEFAULT 'draft', version INTEGER DEFAULT 1,
            accepts TEXT DEFAULT '{}', returns TEXT DEFAULT '{}',
            imports TEXT DEFAULT '[]', tags TEXT DEFAULT '[]',
            spec_ticket TEXT DEFAULT '', spec_summary TEXT DEFAULT '',
            created_at REAL NOT NULL, updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS edges (
            source_id TEXT NOT NULL REFERENCES nodes(id),
            target_id TEXT NOT NULL REFERENCES nodes(id),
            edge_type TEXT NOT NULL,
            PRIMARY KEY (source_id, target_id, edge_type)
        );
        CREATE TABLE IF NOT EXISTS versions (
            node_id     TEXT NOT NULL REFERENCES nodes(id),
            version     INTEGER NOT NULL,
            code        TEXT NOT NULL,
            spec_ticket TEXT DEFAULT '',
            spec_summary TEXT DEFAULT '',
            accepts     TEXT DEFAULT '{}',
            returns     TEXT DEFAULT '{}',
            imports     TEXT DEFAULT '[]',
            task_id     TEXT DEFAULT '',
            status      TEXT DEFAULT 'draft',
            created_at  REAL NOT NULL,
            PRIMARY KEY (node_id, version)
        );
    """)
    return conn


def migrate_versions(conn: sqlite3.Connection) -> int:
    """Migrate existing nodes without versions to v1 golden. Idempotent."""
    rows = conn.execute(
        "SELECT * FROM nodes WHERE id NOT IN (SELECT DISTINCT node_id FROM versions)"
    ).fetchall()
    now = time.time()
    for row in rows:
        conn.execute(
            "INSERT INTO versions (node_id,version,code,spec_ticket,spec_summary,"
            "accepts,returns,imports,task_id,status,created_at) "
            "VALUES (?,1,?,?,?,?,?,?,?,?,?)",
            (row["id"], row["code"], row["spec_ticket"], row["spec_summary"],
             row["accepts"], row["returns"], row["imports"],
             "migration", "golden", now))
        conn.execute(
            "UPDATE nodes SET status='golden', version=1, updated_at=? WHERE id=?",
            (now, row["id"]))
    conn.commit()
    return len(rows)

def create_node(conn: sqlite3.Connection, data: dict) -> dict:
    now = time.time()
    tags = json.dumps(data.get("tags", []))
    conn.execute(
        "INSERT INTO nodes (id,code,language,kind,status,version,accepts,returns,imports,tags,"
        "spec_ticket,spec_summary,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (data["id"], data["code"], data["language"], data["kind"],
         "draft", 1, data.get("accepts", "{}"),
         data.get("returns", "{}"), data.get("imports", "[]"), tags,
         data.get("spec_ticket", ""), data.get("spec_summary", ""), now, now))
    conn.execute(
        "INSERT INTO versions (node_id,version,code,spec_ticket,spec_summary,"
        "accepts,returns,imports,task_id,status,created_at) "
        "VALUES (?,1,?,?,?,?,?,?,?,?,?)",
        (data["id"], data["code"], data.get("spec_ticket", ""),
         data.get("spec_summary", ""), data.get("accepts", "{}"),
         data.get("returns", "{}"), data.get("imports", "[]"),
         data.get("task_id", ""), "draft", now))
    conn.commit()
    return get_node(conn, data["id"])

def get_node(conn: sqlite3.Connection, node_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["tags"] = json.loads(d["tags"])
    d["edges_out"] = [dict(r) for r in conn.execute(
        "SELECT source_id,target_id,edge_type FROM edges WHERE source_id=?", (node_id,))]
    d["edges_in"] = [dict(r) for r in conn.execute(
        "SELECT source_id,target_id,edge_type FROM edges WHERE target_id=?", (node_id,))]
    return d

def delete_node(conn: sqlite3.Connection, node_id: str) -> str | None:
    incoming = conn.execute(
        "SELECT COUNT(*) as c FROM edges WHERE target_id=?", (node_id,)).fetchone()["c"]
    if incoming > 0:
        return f"Cannot delete: node '{node_id}' has {incoming} incoming edge(s)"
    conn.execute("DELETE FROM versions WHERE node_id=?", (node_id,))
    conn.execute("DELETE FROM edges WHERE source_id=?", (node_id,))
    deleted = conn.execute("DELETE FROM nodes WHERE id=?", (node_id,)).rowcount
    conn.commit()
    return None if deleted else f"Node '{node_id}' not found"

def add_edge(conn: sqlite3.Connection, src: str, tgt: str, etype: str) -> dict:
    conn.execute("INSERT INTO edges (source_id,target_id,edge_type) VALUES (?,?,?)", (src, tgt, etype))
    conn.commit()
    return {"source_id": src, "target_id": tgt, "edge_type": etype}

def remove_edge(conn: sqlite3.Connection, src: str, tgt: str, etype: str) -> bool:
    d = conn.execute("DELETE FROM edges WHERE source_id=? AND target_id=? AND edge_type=?",
                     (src, tgt, etype)).rowcount
    conn.commit()
    return d > 0

def get_graph(conn: sqlite3.Connection) -> dict:
    nodes = [r["id"] for r in conn.execute("SELECT id FROM nodes")]
    edges = [dict(r) for r in conn.execute("SELECT source_id,target_id,edge_type FROM edges")]
    return {"nodes": nodes, "edges": edges}

def get_context(conn: sqlite3.Connection, node_id: str) -> dict | None:
    root = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not root:
        return None
    root = dict(root)
    all_ids = {r["id"] for r in conn.execute("SELECT id FROM nodes")}
    visited, frontier, depth = {node_id: 0}, [node_id], 0
    while frontier:
        nxt = []
        for nid in frontier:
            for r in conn.execute(
                    "SELECT target_id FROM edges WHERE source_id=? "
                    "UNION SELECT source_id FROM edges WHERE target_id=?", (nid, nid)):
                if r[0] not in visited:
                    visited[r[0]] = depth + 1; nxt.append(r[0])
        frontier = nxt; depth += 1
    for nid in all_ids - visited.keys():
        visited[nid] = 999
    result = []
    for nid, d in visited.items():
        if d == 0:
            result.append({"id": nid, "depth": 0, "code": root["code"],
                           "spec_ticket": root["spec_ticket"], "spec_summary": root["spec_summary"],
                           "accepts": root["accepts"], "returns": root["returns"]})
        elif d == 1:
            row = conn.execute("SELECT spec_summary,accepts,returns FROM nodes WHERE id=?", (nid,)).fetchone()
            result.append({"id": nid, "depth": 1, "spec_summary": row["spec_summary"],
                           "accepts": row["accepts"], "returns": row["returns"]})
        elif d == 2:
            row = conn.execute("SELECT spec_ticket FROM nodes WHERE id=?", (nid,)).fetchone()
            result.append({"id": nid, "depth": 2, "spec_ticket": row["spec_ticket"]})
        else:
            result.append({"id": nid, "depth": d})
    return {"target": node_id, "nodes": result}

def _sync_version_to_node(conn: sqlite3.Connection, node_id: str, ver: dict):
    """Sync a version's fields into the nodes cache row."""
    conn.execute(
        "UPDATE nodes SET code=?, spec_ticket=?, spec_summary=?, accepts=?, returns=?, "
        "imports=?, status=?, version=?, updated_at=? WHERE id=?",
        (ver["code"], ver["spec_ticket"], ver["spec_summary"],
         ver["accepts"], ver["returns"], ver["imports"],
         ver["status"], ver["version"], time.time(), node_id))


def create_version(conn: sqlite3.Connection, node_id: str, data: dict) -> dict | None:
    if not conn.execute("SELECT id FROM nodes WHERE id=?", (node_id,)).fetchone():
        return None
    max_v = conn.execute(
        "SELECT COALESCE(MAX(version),0) FROM versions WHERE node_id=?", (node_id,)
    ).fetchone()[0]
    new_v = max_v + 1
    now = time.time()
    conn.execute(
        "INSERT INTO versions (node_id,version,code,spec_ticket,spec_summary,"
        "accepts,returns,imports,task_id,status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (node_id, new_v, data["code"], data.get("spec_ticket", ""),
         data.get("spec_summary", ""), data.get("accepts", "{}"),
         data.get("returns", "{}"), data.get("imports", "[]"),
         data.get("task_id", ""), "draft", now))
    golden = conn.execute(
        "SELECT version FROM versions WHERE node_id=? AND status='golden'", (node_id,)
    ).fetchone()
    if not golden:
        ver = dict(conn.execute(
            "SELECT * FROM versions WHERE node_id=? AND version=?", (node_id, new_v)
        ).fetchone())
        _sync_version_to_node(conn, node_id, ver)
    conn.commit()
    return dict(conn.execute(
        "SELECT * FROM versions WHERE node_id=? AND version=?", (node_id, new_v)
    ).fetchone())


def promote_version(conn: sqlite3.Connection, node_id: str) -> dict | str:
    """Promote latest draft → golden. Returns version dict or error string."""
    draft = conn.execute(
        "SELECT * FROM versions WHERE node_id=? AND status='draft' ORDER BY version DESC LIMIT 1",
        (node_id,)
    ).fetchone()
    if not draft:
        return "no_draft"
    draft = dict(draft)
    conn.execute(
        "UPDATE versions SET status='deprecated' WHERE node_id=? AND status='golden'",
        (node_id,))
    conn.execute(
        "UPDATE versions SET status='golden' WHERE node_id=? AND version=?",
        (node_id, draft["version"]))
    draft["status"] = "golden"
    _sync_version_to_node(conn, node_id, draft)
    conn.commit()
    return draft


def reject_version(conn: sqlite3.Connection, node_id: str) -> dict | str:
    """Reject latest draft. Returns version dict or error string."""
    draft = conn.execute(
        "SELECT * FROM versions WHERE node_id=? AND status='draft' ORDER BY version DESC LIMIT 1",
        (node_id,)
    ).fetchone()
    if not draft:
        return "no_draft"
    draft = dict(draft)
    conn.execute(
        "UPDATE versions SET status='rejected' WHERE node_id=? AND version=?",
        (node_id, draft["version"]))
    draft["status"] = "rejected"
    golden = conn.execute(
        "SELECT version FROM versions WHERE node_id=? AND status='golden'", (node_id,)
    ).fetchone()
    if not golden:
        _sync_version_to_node(conn, node_id, draft)
    conn.commit()
    return draft


def get_versions(conn: sqlite3.Connection, node_id: str) -> list[dict] | None:
    if not conn.execute("SELECT id FROM nodes WHERE id=?", (node_id,)).fetchone():
        return None
    return [dict(r) for r in conn.execute(
        "SELECT * FROM versions WHERE node_id=? ORDER BY version", (node_id,))]


def get_version(conn: sqlite3.Connection, node_id: str, version: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM versions WHERE node_id=? AND version=?", (node_id, version)
    ).fetchone()
    return dict(row) if row else None


def search_nodes(conn: sqlite3.Connection, query: str) -> list[dict]:
    p = f"%{query}%"
    return [dict(r) for r in conn.execute(
        "SELECT id,spec_ticket FROM nodes WHERE id LIKE ? OR spec_ticket LIKE ?", (p, p))]
