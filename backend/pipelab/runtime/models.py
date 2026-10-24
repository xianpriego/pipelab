"""API models of the pipeline runtime."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from pipelab.catalog.models import PropertyValue
from pipelab.graph.models import Graph

RuntimeState = Literal["idle", "starting", "ready", "paused", "playing", "stopping", "stopped", "error"]


class RuntimeStatus(BaseModel):
    project_id: str
    state: RuntimeState = "idle"
    started_at: float | None = None
    error: str | None = None


class StartRequest(BaseModel):
    """Start the saved graph, or ``graph`` when given (unsaved edits)."""

    graph: Graph | None = None
    gst_debug: str | None = None


class StopRequest(BaseModel):
    mode: Literal["eos", "kill"] = "eos"


class PropertyChange(BaseModel):
    node_id: str
    property: str
    value: PropertyValue
    pad: str | None = None


class LinkToggle(BaseModel):
    """Attach (or with ``enabled=false`` remove) a tap or a probe on a link."""

    edge_id: str
    enabled: bool = True
