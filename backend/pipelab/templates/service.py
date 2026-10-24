"""Starter templates resolved against the catalog of this machine."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pipelab.catalog.store import Catalog
from pipelab.graph.models import Graph
from pipelab.importer.gst_launch import import_gst_launch
from pipelab.templates.starters import STARTERS, Starter


class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    available: bool
    missing: list[str] = Field(default_factory=list)


class TemplateNotFound(KeyError):
    pass


class TemplateService:
    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        self._graphs: dict[str, Graph] = {}

    def _graph(self, starter: Starter) -> Graph:
        if starter.id not in self._graphs:
            self._graphs[starter.id] = import_gst_launch(starter.pipeline, self._catalog).graph
        return self._graphs[starter.id]

    def list(self) -> list[TemplateInfo]:
        templates = []
        for starter in STARTERS:
            missing = sorted(
                {n.factory for n in self._graph(starter).nodes if n.factory not in self._catalog}
            )
            templates.append(
                TemplateInfo(
                    id=starter.id,
                    name=starter.name,
                    description=starter.description,
                    available=not missing,
                    missing=missing,
                )
            )
        return templates

    def graph(self, template_id: str) -> Graph:
        starter = next((s for s in STARTERS if s.id == template_id), None)
        if starter is None:
            raise TemplateNotFound(template_id)
        return self._graph(starter).model_copy(deep=True)
