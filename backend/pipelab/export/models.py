"""API models for exporting pipelines."""

from __future__ import annotations

from pydantic import BaseModel

from pipelab.graph.models import Graph


class ExportFormat(BaseModel):
    id: str
    label: str
    language: str
    extension: str
    description: str


class ExportRequest(BaseModel):
    graph: Graph
    format: str
    name: str = "pipeline"


class ExportResult(BaseModel):
    format: str
    filename: str
    language: str
    content: str
