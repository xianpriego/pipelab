"""Pipeline exporters: gst-launch, Python, C, Rust and Pipelab JSON."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pipelab.catalog.store import Catalog
from pipelab.components.models import Component
from pipelab.export import (
    c_code,
    gst_launch,
    json_doc,
    python_code,
    python_dynamic,
    rust_code,
    rust_dynamic,
)
from pipelab.export.common import slug
from pipelab.export.flatten import dynamic_notes, flatten
from pipelab.export.models import ExportFormat, ExportResult
from pipelab.export.plan import uses_dynamic_features
from pipelab.export.script_notes import comment_block
from pipelab.graph.models import Graph

Renderer = Callable[[Graph, Catalog, str, Mapping[str, Component]], str]

FORMATS: list[ExportFormat] = [
    ExportFormat(
        id="gst-launch",
        label="gst-launch-1.0",
        language="bash",
        extension="sh",
        description="Command line to try the pipeline in a terminal.",
    ),
    ExportFormat(
        id="python",
        label="Python (PyGObject)",
        language="python",
        extension="py",
        description="Runnable class that builds every element explicitly; easy to embed.",
    ),
    ExportFormat(
        id="c",
        label="C (GStreamer API)",
        language="c",
        extension="c",
        description="Single-file C program with bus handling and dynamic pad linking.",
    ),
    ExportFormat(
        id="rust",
        label="Rust (gstreamer-rs)",
        language="rust",
        extension="rs",
        description="main.rs for a cargo project using the gstreamer crate.",
    ),
    ExportFormat(
        id="json",
        label="Pipelab JSON",
        language="json",
        extension="json",
        description="Graph document that can be imported back into Pipelab.",
    ),
]


def _static(render: Callable[[Graph, Catalog, str], str], style: str) -> Renderer:
    """gst-launch and C: components are expanded, dynamic parts become notes."""

    def renderer(graph: Graph, catalog: Catalog, name: str, components: Mapping[str, Component]) -> str:
        notes = comment_block(dynamic_notes(graph, components), style)
        return render(flatten(graph, components), catalog, name) + notes

    return renderer


def _library(
    simple: Callable[[Graph, Catalog, str], str],
    dynamic: Callable[[Graph, Catalog, str, Mapping[str, Component]], str],
) -> Renderer:
    """Python and Rust: a library with components, slots, functions and probes when used."""

    def renderer(graph: Graph, catalog: Catalog, name: str, components: Mapping[str, Component]) -> str:
        if uses_dynamic_features(graph):
            return dynamic(graph, catalog, name, components)
        return simple(graph, catalog, name)

    return renderer


_RENDERERS: dict[str, Renderer] = {
    "gst-launch": _static(gst_launch.render, "shell"),
    "python": _library(python_code.render, python_dynamic.render),
    "c": _static(c_code.render, "c"),
    "rust": _library(rust_code.render, rust_dynamic.render),
    "json": lambda graph, catalog, name, _components: json_doc.render(graph, catalog, name),
}


def _filename(format_id: str, name: str) -> str:
    if format_id == "rust":
        return "main.rs"
    if format_id == "json":
        return f"{slug(name)}.pipelab.json"
    extension = next(f.extension for f in FORMATS if f.id == format_id)
    return f"{slug(name)}.{extension}"


def export_graph(
    graph: Graph,
    catalog: Catalog,
    format_id: str,
    name: str = "pipeline",
    components: Mapping[str, Component] | None = None,
) -> ExportResult:
    """Render ``graph`` in ``format_id``; raises ``KeyError`` for unknown formats.

    ``components`` are the library definitions of the component instances
    (``component:<id>`` nodes) and slots used by the graph.
    """
    renderer = _RENDERERS[format_id]
    language = next(f.language for f in FORMATS if f.id == format_id)
    return ExportResult(
        format=format_id,
        filename=_filename(format_id, name),
        language=language,
        content=renderer(graph, catalog, name, components or {}),
    )


__all__ = ["FORMATS", "export_graph"]
