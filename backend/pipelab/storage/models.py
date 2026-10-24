"""Project models persisted by the storage layer."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from pipelab.graph.models import Graph


class ProjectSettings(BaseModel):
    gst_debug: str = "*:2"


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: datetime
    updated_at: datetime
    graph: Graph = Field(default_factory=Graph)
    settings: ProjectSettings = Field(default_factory=ProjectSettings)


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: datetime
    updated_at: datetime
    node_count: int = 0


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    template: str | None = None
    graph: Graph | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph: Graph | None = None
    settings: ProjectSettings | None = None
