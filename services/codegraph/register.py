"""Self-registration in MCGK on startup."""
from __future__ import annotations
import logging
import httpx

log = logging.getLogger("codegraph")

ENDPOINTS = [
    {"path": "/node", "method": "POST", "description": "Create a code node",
     "accepts": {"id": "str", "code": "str", "language": "str", "kind": "str"}, "returns": {"node": "object"}},
    {"path": "/node/{id}", "method": "GET", "description": "Get node with edges",
     "accepts": None, "returns": {"node": "object"}},
    {"path": "/node/{id}", "method": "PUT", "description": "Update node",
     "accepts": {"code": "str?", "language": "str?"}, "returns": {"node": "object"}},
    {"path": "/node/{id}", "method": "DELETE", "description": "Delete node (fails if incoming edges)",
     "accepts": None, "returns": {"ok": "bool"}},
    {"path": "/edge", "method": "POST", "description": "Add edge",
     "accepts": {"source_id": "str", "target_id": "str", "edge_type": "str"}, "returns": {"edge": "object"}},
    {"path": "/edge", "method": "DELETE", "description": "Remove edge",
     "accepts": {"source_id": "str", "target_id": "str", "edge_type": "str"}, "returns": {"ok": "bool"}},
    {"path": "/graph", "method": "GET", "description": "All node ids and edges",
     "accepts": None, "returns": {"nodes": "list", "edges": "list"}},
    {"path": "/context/{id}", "method": "GET", "description": "Dunbar-circle context for a node",
     "accepts": None, "returns": {"target": "str", "nodes": "list"}},
    {"path": "/search", "method": "GET", "description": "Search nodes by id or spec_ticket",
     "accepts": {"query": "str"}, "returns": {"results": "list"}},
]

def register_with_mcgk(mcgk_url: str, host: str, port: int) -> bool:
    address = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}"
    payload = {
        "name": "codegraph", "address": address,
        "description": "Code-as-graph storage. Manages code nodes, edges, and Dunbar-circle context.",
        "endpoints": ENDPOINTS,
    }
    try:
        resp = httpx.post(f"{mcgk_url}/register", json=payload, timeout=5.0)
        resp.raise_for_status()
        log.info("Registered with MCGK at %s", mcgk_url)
        return True
    except Exception as exc:
        log.warning("MCGK registration failed (%s) — continuing without it", exc)
        return False
