"""Pipelab's own re-importable JSON document."""

from __future__ import annotations

import json

from pipelab.catalog.store import Catalog
from pipelab.graph.models import Graph

DOCUMENT_FORMAT = "pipelab/graph@1"


def render(graph: Graph, catalog: Catalog, name: str) -> str:
    del catalog  # the document is catalog independent
    document = {"format": DOCUMENT_FORMAT, "name": name, "graph": graph.model_dump(mode="json")}
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
