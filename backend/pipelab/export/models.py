"""API models for exporting and importing pipelines."""

from __future__ import annotations

from pydantic import BaseModel, Field

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


class ImportRequest(BaseModel):
    description: str


class ImportResult(BaseModel):
    graph: Graph
    warnings: list[str] = Field(default_factory=list)
