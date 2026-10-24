"""Pipeline exporters: gst-launch, Python, C, Rust and Pipelab JSON."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pipelab.catalog.store import Catalog
from pipelab.components.models import Component
from pipelab.export import c_code, gst_launch, json_doc, python_code, rust_code
from pipelab.export.common import slug
from pipelab.export.flatten import flatten
from pipelab.export.models import ExportFormat, ExportResult
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
        description="Library: a class owning the pipeline and one builder per component; runnable.",
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
        description="main.rs library: a type owning the pipeline and one builder per component.",
    ),
    ExportFormat(
        id="json",
        label="Pipelab JSON",
        language="json",
        extension="json",
        description="Graph document that can be imported back into Pipelab.",
    ),
]


def _flattened(render: Callable[[Graph, Catalog, str], str]) -> Renderer:
    """gst-launch and C cannot express bins: component instances are expanded into elements."""

    def renderer(graph: Graph, catalog: Catalog, name: str, components: Mapping[str, Component]) -> str:
        return render(flatten(graph, components), catalog, name)

    return renderer


_RENDERERS: dict[str, Renderer] = {
    "gst-launch": _flattened(gst_launch.render),
    "python": python_code.render,
    "c": _flattened(c_code.render),
    "rust": rust_code.render,
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
    (``component:<id>`` nodes) used by the graph.
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
