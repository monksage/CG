"""CodeGraph — minimal code-as-graph service."""
from __future__ import annotations
import os, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
import uvicorn
from db import (connect, migrate_versions, create_node, get_node, delete_node,
                add_edge, remove_edge, get_graph, get_context, search_nodes,
                create_version, promote_version, reject_version, get_versions, get_version)
from models import (NodeCreate, NodeResponse, EdgeRequest, EdgeResponse,
                    GraphResponse, ContextResponse, SearchResult,
                    VersionCreate, VersionResponse)
from register import register_with_mcgk

PORT = int(os.environ.get("CODEGRAPH_PORT", "39051"))
HOST = os.environ.get("CODEGRAPH_HOST", "0.0.0.0")
DB_PATH = os.environ.get("CODEGRAPH_DB_PATH", "codegraph.db")
MCGK_URL = os.environ.get("MCGK_URL", "http://localhost:39050")
logging.basicConfig(level=logging.INFO)
_state = {}

def _db():
    return _state["conn"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["conn"] = connect(DB_PATH)
    count = migrate_versions(_state["conn"])
    if count:
        logging.info("Migrated %d nodes to version 1 golden", count)
    register_with_mcgk(MCGK_URL, HOST, PORT)
    yield
    _state["conn"].close()

app = FastAPI(title="CodeGraph", lifespan=lifespan)

@app.post("/node", response_model=NodeResponse)
def api_create_node(body: NodeCreate):
    try:
        return create_node(_db(), body.model_dump())
    except Exception as exc:
        raise HTTPException(400, str(exc))

@app.get("/node/{node_id}", response_model=NodeResponse)
def api_get_node(node_id: str):
    result = get_node(_db(), node_id)
    if not result:
        raise HTTPException(404, f"Node '{node_id}' not found")
    return result

@app.delete("/node/{node_id}")
def api_delete_node(node_id: str):
    error = delete_node(_db(), node_id)
    if error:
        raise HTTPException(409 if "incoming" in error else 404, error)
    return {"ok": True}

@app.post("/edge", response_model=EdgeResponse)
def api_add_edge(body: EdgeRequest):
    try:
        return add_edge(_db(), body.source_id, body.target_id, body.edge_type)
    except Exception as exc:
        raise HTTPException(400, str(exc))

@app.delete("/edge")
def api_remove_edge(body: EdgeRequest):
    if not remove_edge(_db(), body.source_id, body.target_id, body.edge_type):
        raise HTTPException(404, "Edge not found")
    return {"ok": True}

@app.get("/graph", response_model=GraphResponse)
def api_graph():
    return get_graph(_db())

@app.get("/context/{node_id}", response_model=ContextResponse)
def api_context(node_id: str):
    result = get_context(_db(), node_id)
    if not result:
        raise HTTPException(404, f"Node '{node_id}' not found")
    return result

@app.get("/search", response_model=list[SearchResult])
def api_search(query: str = Query(..., min_length=1)):
    return search_nodes(_db(), query)


@app.post("/node/{node_id}/version", response_model=VersionResponse)
def api_create_version(node_id: str, body: VersionCreate):
    result = create_version(_db(), node_id, body.model_dump())
    if result is None:
        raise HTTPException(404, f"Node '{node_id}' not found")
    return result


@app.post("/node/{node_id}/promote", response_model=VersionResponse)
def api_promote(node_id: str):
    result = promote_version(_db(), node_id)
    if result == "no_draft":
        raise HTTPException(409, f"No draft version to promote for '{node_id}'")
    return result


@app.post("/node/{node_id}/reject", response_model=VersionResponse)
def api_reject(node_id: str):
    result = reject_version(_db(), node_id)
    if result == "no_draft":
        raise HTTPException(409, f"No draft version to reject for '{node_id}'")
    return result


@app.get("/node/{node_id}/versions", response_model=list[VersionResponse])
def api_get_versions(node_id: str):
    result = get_versions(_db(), node_id)
    if result is None:
        raise HTTPException(404, f"Node '{node_id}' not found")
    return result


@app.get("/node/{node_id}/version/{version}", response_model=VersionResponse)
def api_get_version(node_id: str, version: int):
    result = get_version(_db(), node_id, version)
    if not result:
        raise HTTPException(404, f"Version {version} not found for '{node_id}'")
    return result


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, log_level="info")
