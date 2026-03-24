"""
Pydantic models — strict separation between internal and external.

External (contour-facing):
  - No address, no port, no health internals. Only schema + description.

Internal (MCGK-only):
  - Routing info, health state, timestamps. Never serialized to contours.
"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# EXTERNAL — visible to contours via /discover and /map
# ═══════════════════════════════════════════════════════════════════════

class EndpointSpec(BaseModel):
    """One endpoint a contour exposes — schema only, no location info."""

    path: str = Field(..., description="URL path relative to contour root, e.g. /translate")
    method: str = Field(..., description="HTTP method: GET, POST, PUT, DELETE, etc.")
    description: str = Field(..., description="Human-readable: what does this endpoint do?")
    accepts: dict[str, Any] | None = Field(
        None,
        description="JSON-schema-style description of the request body (null if none)",
    )
    returns: dict[str, Any] | None = Field(
        None,
        description="JSON-schema-style description of the response body (null if none)",
    )


class ExternalPassport(BaseModel):
    """What another contour receives from discovery.

    Contains everything needed to *understand* the interface,
    but nothing about *where* it lives. Routing goes through MCGK.
    """

    name: str = Field(..., description="Unique contour identifier")
    description: str = Field(..., description="Human-readable: what does this contour do?")
    endpoints: list[EndpointSpec] = Field(
        ..., min_length=1, description="Endpoints the contour exposes"
    )


# ═══════════════════════════════════════════════════════════════════════
# REGISTRATION — what a contour sends when registering
# ═══════════════════════════════════════════════════════════════════════

class RegistrationRequest(BaseModel):
    """POST /register body. Includes address (MCGK needs it internally),
    but MCGK never forwards the address to other contours."""

    name: str = Field(..., description="Unique contour name")
    address: str = Field(
        ..., description="Base URL where the contour runs (MCGK-internal, never exposed)"
    )
    description: str = Field(..., description="Human-readable purpose")
    endpoints: list[EndpointSpec] = Field(..., min_length=1, description="At least one endpoint")


# ═══════════════════════════════════════════════════════════════════════
# INTERNAL — MCGK-only, never serialized to contours
# ═══════════════════════════════════════════════════════════════════════

class InternalRecord(BaseModel):
    """What MCGK stores per contour. Never sent to other contours."""

    name: str
    address: str
    description: str
    endpoints: list[EndpointSpec]
    healthy: bool = True
    registered_at: float = Field(default_factory=time.time)
    last_health_check: float | None = None

    def to_external(self) -> ExternalPassport:
        """Strip internal fields, return only what contours should see."""
        return ExternalPassport(
            name=self.name,
            description=self.description,
            endpoints=self.endpoints,
        )


# ═══════════════════════════════════════════════════════════════════════
# OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════

class RequestLog(BaseModel):
    """One proxied request."""

    timestamp: float = Field(default_factory=time.time)
    source: str | None = None
    target: str = ""
    target_path: str = ""
    method: str = ""
    status_code: int | None = None
    error: str | None = None
    duration_ms: float | None = None
