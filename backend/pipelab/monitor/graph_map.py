"""Map a :class:`ParsedPipeline` (from a ``.dot`` dump) onto read-only monitor models.

Element GObject type names are resolved to factory names against this machine's catalog, so the
monitor view can reuse the editor's node rendering (icon, family colour, element docs). When the
factory is not on this machine the node is still shown, keyed by its GType.
"""

from __future__ import annotations

from pipelab.graph.layout import auto_layout
from pipelab.graph.models import Edge, Graph, Node
from pipelab.monitor.dot_parse import ParsedPipeline
from pipelab.monitor.models import MonitorEdge, MonitorNode, MonitorPipeline, MonitorSource


def build_gtype_index(catalog_elements: list) -> dict[str, str]:
    """``{GObject type name: factory name}`` from catalog ``ElementInfo``/``ElementSummary``.

    ``hierarchy[0]`` is the concrete type; summaries without a hierarchy fall back to the
    conventional ``Gst<Name>`` form so common elements still resolve from a summary-only catalog.
    """
    index: dict[str, str] = {}
    for element in catalog_elements:
        name = getattr(element, "name", None)
        if not name or name.startswith("component:"):
            continue
        hierarchy = getattr(element, "hierarchy", None) or []
        if hierarchy:
            index.setdefault(hierarchy[0], name)
        guessed = "Gst" + "".join(part.capitalize() for part in name.split("-"))
        index.setdefault(guessed, name)
    return index


def _resolve_factory(gtype: str, element_name: str, index: dict[str, str]) -> tuple[str, bool]:
    if gtype in index:
        return index[gtype], True
    # Fall back to the default naming convention: a gst-launch name is "<factory><n>".
    guessed = element_name.rstrip("0123456789")
    if guessed in index.values():
        return guessed, True
    return guessed or element_name, False


def to_monitor_pipeline(
    parsed: ParsedPipeline, source: MonitorSource, gtype_index: dict[str, str] | None = None
) -> MonitorPipeline:
    index = gtype_index or {}
    bins = {element.parent for element in parsed.elements.values() if element.parent}

    nodes: list[MonitorNode] = []
    for addr, element in parsed.elements.items():
        factory, known = _resolve_factory(element.gtype, element.name, index)
        nodes.append(
            MonitorNode(
                id=addr,
                name=element.name,
                gtype=element.gtype,
                factory=factory,
                factory_known=known,
                state=element.state,
                is_bin=addr in bins,
                parent=element.parent,
                properties=dict(element.properties),
            )
        )

    edges: list[MonitorEdge] = []
    for i, link in enumerate(parsed.links):
        if link.src_element not in parsed.elements or link.dst_element not in parsed.elements:
            continue
        edges.append(
            MonitorEdge(
                id=f"e{i}",
                source=link.src_element,
                source_pad=link.src_pad,
                target=link.dst_element,
                target_pad=link.dst_pad,
                caps=link.caps,
            )
        )

    _place(nodes, edges)
    return MonitorPipeline(name=parsed.name, source=source, nodes=nodes, edges=edges)


def _place(nodes: list[MonitorNode], edges: list[MonitorEdge]) -> None:
    """Position nodes with the editor's layered layout, laying out each bin's children among their
    siblings (nesting is flattened for placement; the ``parent`` field keeps the hierarchy)."""
    if not nodes:
        return
    graph = Graph(
        nodes=[Node(id=n.id, factory=n.factory or "unknown", name=n.name) for n in nodes],
        edges=[
            Edge(id=e.id, source=e.source, source_pad=e.source_pad, target=e.target, target_pad=e.target_pad)
            for e in edges
        ],
    )
    placed = auto_layout(graph)
    by_id = {node.id: node.position for node in placed.nodes}
    for node in nodes:
        pos = by_id.get(node.id)
        if pos:
            node.position = {"x": pos.x, "y": pos.y}
