"""What the UI lists for ready-made things (project templates, starter components)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pipelab.catalog.store import Catalog
from pipelab.graph.models import Graph


class StarterInfo(BaseModel):
    id: str
    name: str
    description: str
    available: bool
    missing: list[str] = Field(default_factory=list)  # elements not installed on this machine


def starter_info(starter_id: str, name: str, description: str, graph: Graph, catalog: Catalog) -> StarterInfo:
    missing = sorted({node.factory for node in graph.nodes if node.factory not in catalog})
    return StarterInfo(
        id=starter_id, name=name, description=description, available=not missing, missing=missing
    )
