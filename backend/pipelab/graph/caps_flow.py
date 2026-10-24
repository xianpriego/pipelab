"""Static propagation of *effective caps* through a graph.

Template caps alone are too permissive: ``queue`` accepts ANY, so a link
``queue ! autoaudiosink`` would look fine even when the queue carries H.264.
This module narrows each pad's caps with what flows into it:

* caps-agnostic elements (queue, tee, identity…) forward their input caps;
* ``capsfilter`` intersects its input with its ``caps`` property;
* sources with a ``caps`` property (appsrc, udpsrc…) produce at most that.
"""

from __future__ import annotations

import re

from pipelab.catalog.models import ElementInfo
from pipelab.catalog.store import Catalog, parse_caps
from pipelab.graph.models import Graph, Node
from pipelab.gst import Gst

PASSTHROUGH = {
    "queue",
    "queue2",
    "multiqueue",
    "tee",
    "identity",
    "valve",
    "input-selector",
    "output-selector",
    "funnel",
    "concat",
    "clocksync",
    "progressreport",
    "watchdog",
    "livesync",
    "fallbackswitch",
    "ts-queue",
}
CAPS_FILTERS = {"capsfilter"}
QUEUE_LIKE = {"queue", "queue2", "multiqueue", "ts-queue"}
_INDEXED = {"multiqueue"}
_INDEX = re.compile(r"_(\d+)$")


def _intersect(a: Gst.Caps, b: Gst.Caps) -> Gst.Caps:
    if a.is_any():
        return b
    if b.is_any():
        return a
    return a.intersect_full(b, Gst.CapsIntersectMode.FIRST)


def _union(caps_list: list[Gst.Caps]) -> Gst.Caps:
    if any(caps.is_any() for caps in caps_list):
        return Gst.Caps.new_any()
    result = Gst.Caps.new_empty()
    for caps in caps_list:
        result = result.merge(caps.copy())
    return result


def is_passthrough(element: ElementInfo | None) -> bool:
    return element is not None and (element.name in PASSTHROUGH or element.name in CAPS_FILTERS)


class CapsFlow:
    """Computes effective caps for output pads and accepted caps for input pads."""

    def __init__(self, graph: Graph, catalog: Catalog) -> None:
        self.graph = graph
        self.catalog = catalog
        self._nodes = {node.id: node for node in graph.nodes}
        self._cache: dict[tuple[str, str], Gst.Caps] = {}
        self._visiting: set[tuple[str, str]] = set()

    def _caps_property(self, node: Node) -> Gst.Caps | None:
        value = node.properties.get("caps")
        if not isinstance(value, str) or not value.strip():
            return None
        caps = Gst.Caps.from_string(value)
        return caps if caps is not None else None

    def input_caps(self, node_id: str, pad: str) -> Gst.Caps:
        """Caps a sink pad can accept."""
        node = self._nodes.get(node_id)
        if node is None:
            return Gst.Caps.new_any()
        caps = self.catalog.template_caps(node.factory, pad)
        constraint = self._caps_property(node)
        if constraint is not None and node.factory in CAPS_FILTERS | {"appsink"}:
            caps = _intersect(caps, constraint)
        return caps

    def output_caps(self, node_id: str, pad: str) -> Gst.Caps:
        """Caps that can come out of a src pad given everything upstream."""
        key = (node_id, pad)
        if key in self._cache:
            return self._cache[key]
        node = self._nodes.get(node_id)
        if node is None:
            return Gst.Caps.new_any()
        if key in self._visiting:
            return self.catalog.template_caps(node.factory, pad)
        self._visiting.add(key)
        try:
            caps = self._compute_output(node, pad)
        finally:
            self._visiting.discard(key)
        self._cache[key] = caps
        return caps

    def _compute_output(self, node: Node, pad: str) -> Gst.Caps:
        template = self.catalog.template_caps(node.factory, pad)
        constraint = self._caps_property(node)
        element = self.catalog.get(node.factory)
        if is_passthrough(element):
            upstream = self._upstream_caps(node, pad)
            caps = template if upstream is None else _intersect(upstream, template)
            if node.factory in CAPS_FILTERS and constraint is not None:
                caps = _intersect(caps, constraint)
            return caps
        if constraint is not None and element is not None and "source" in element.categories:
            return _intersect(template, constraint)
        return template

    def _upstream_caps(self, node: Node, pad: str) -> Gst.Caps | None:
        edges = self.graph.incoming(node.id)
        if node.factory in _INDEXED:
            match = _INDEX.search(pad)
            edges = [e for e in edges if match and e.target_pad.endswith(f"_{match.group(1)}")]
        if not edges:
            return None
        return _union([self.output_caps(e.source, e.source_pad) for e in edges])


def caps_to_string(caps: Gst.Caps, limit: int = 4000) -> str:
    text = caps.to_string()
    return text if len(text) <= limit else text[:limit] + "…"


__all__ = ["CAPS_FILTERS", "PASSTHROUGH", "QUEUE_LIKE", "CapsFlow", "caps_to_string", "parse_caps"]
