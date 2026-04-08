"""Pydantic models for CodeGraph API."""
from __future__ import annotations
from pydantic import BaseModel, Field


class NodeCreate(BaseModel):
    id: str
    code: str
    language: str
    kind: str
    accepts: str = "{}"
    returns: str = "{}"
    imports: str = "[]"
    tags: list[str] = Field(default_factory=list)
    spec_ticket: str = ""
    spec_summary: str = ""
    task_id: str = ""


class VersionCreate(BaseModel):
    code: str
    spec_ticket: str = ""
    spec_summary: str = ""
    accepts: str = "{}"
    returns: str = "{}"
    imports: str = "[]"
    task_id: str = ""


class VersionResponse(BaseModel):
    node_id: str
    version: int
    code: str
    spec_ticket: str
    spec_summary: str
    accepts: str
    returns: str
    imports: str
    task_id: str
    status: str
    created_at: float

class EdgeRequest(BaseModel):
    source_id: str
    target_id: str
    edge_type: str

class NodeResponse(BaseModel):
    id: str
    code: str
    language: str
    kind: str
    status: str
    version: int
    accepts: str
    returns: str
    imports: str
    tags: list[str]
    spec_ticket: str
    spec_summary: str
    created_at: float
    updated_at: float
    edges_out: list[EdgeResponse] = Field(default_factory=list)
    edges_in: list[EdgeResponse] = Field(default_factory=list)

class EdgeResponse(BaseModel):
    source_id: str
    target_id: str
    edge_type: str

class GraphResponse(BaseModel):
    nodes: list[str]
    edges: list[EdgeResponse]

class ContextNode(BaseModel):
    id: str
    depth: int
    code: str | None = None
    spec_ticket: str | None = None
    spec_summary: str | None = None
    accepts: str | None = None
    returns: str | None = None

class ContextResponse(BaseModel):
    target: str
    nodes: list[ContextNode]

class SearchResult(BaseModel):
    id: str
    spec_ticket: str
