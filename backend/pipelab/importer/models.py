"""API models for importing gst-launch descriptions."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pipelab.graph.models import Graph


class ImportRequest(BaseModel):
    description: str


class ImportResult(BaseModel):
    graph: Graph
    warnings: list[str] = Field(default_factory=list)
