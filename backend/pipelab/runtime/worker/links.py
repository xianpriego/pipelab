"""Links graph edges between real pads, including request and dynamic pads."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pipelab.catalog.store import template_regex
from pipelab.graph.models import Edge, Graph, Node
from pipelab.gst import Gst
from pipelab.runtime.worker.diagnose import mismatch

Emit = Callable[[dict[str, Any]], None]
OnLinked = Callable[[Edge, Gst.Pad], None]


def _template(element: Gst.Element, pad_name: str) -> Gst.StaticPadTemplate | None:
    templates = element.get_factory().get_static_pad_templates() if element.get_factory() else []
    for template in templates:
        if template.name_template == pad_name:
            return template
    for template in templates:
        if template.presence != Gst.PadPresence.ALWAYS and template_regex(template.name_template).match(
            pad_name
        ):
            return template
    return None


def get_pad(element: Gst.Element, pad_name: str) -> Gst.Pad | None:
    """Existing pad, or a newly requested one for request templates."""
    pad = element.get_static_pad(pad_name)
    if pad is not None:
        return pad
    template = _template(element, pad_name)
    if template is not None and template.presence == Gst.PadPresence.REQUEST:
        return element.request_pad_simple(pad_name)
    return None


def apply_pad_properties(node: Node, pad: Gst.Pad, emit: Emit) -> None:
    for name, value in node.pad_properties.get(pad.get_name(), {}).items():
        if pad.find_property(name) is None:
            emit(
                {
                    "type": "bus",
                    "kind": "warning",
                    "source": node.name,
                    "node_id": node.id,
                    "text": f"Pad {pad.get_name()} has no property '{name}'",
                }
            )
            continue
        Gst.util_set_object_arg(pad, name, _launch_value(value))


def _launch_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class Linker:
    def __init__(
        self,
        graph: Graph,
        elements: dict[str, Gst.Element],
        emit: Emit,
        on_linked: OnLinked,
        prefix: str = "",
    ) -> None:
        self._prefix = prefix  # makes node ids in events global (component instances)
        self._graph = graph
        self._elements = elements
        self._emit = emit
        self._on_linked = on_linked
        self._pending: dict[str, list[Edge]] = {}

    def _node(self, node_id: str) -> Node:
        node = self._graph.node(node_id)
        assert node is not None
        return node

    def _sink_pad(self, edge: Edge) -> Gst.Pad | None:
        target = self._elements[edge.target]
        pad = get_pad(target, edge.target_pad)
        if pad is not None:
            apply_pad_properties(self._node(edge.target), pad, self._emit)
        return pad

    def link_all(self) -> list[str]:
        """Link every edge whose source pad exists; returns error messages."""
        errors = []
        for edge in self._graph.edges:
            source = self._elements[edge.source]
            src_pad = get_pad(source, edge.source_pad)
            if src_pad is None:
                self._pending.setdefault(edge.source, []).append(edge)
                continue
            apply_pad_properties(self._node(edge.source), src_pad, self._emit)
            error = self._link(edge, src_pad)
            if error:
                errors.append(error)
        for node_id in self._pending:
            self._elements[node_id].connect("pad-added", self._on_pad_added, node_id)
            self._elements[node_id].connect("no-more-pads", self._on_no_more_pads, node_id)
        return errors

    def _link(self, edge: Edge, src_pad: Gst.Pad) -> str | None:
        sink_pad = self._sink_pad(edge)
        source, target = self._node(edge.source), self._node(edge.target)
        if sink_pad is None:
            return f"{target.name} has no pad '{edge.target_pad}'"
        result = src_pad.link(sink_pad)
        if result != Gst.PadLinkReturn.OK:
            return (
                f"Cannot link {source.name}.{src_pad.get_name()} → {target.name}.{sink_pad.get_name()}: "
                f"{result.value_nick}"
            )
        self._on_linked(edge, src_pad)
        return None

    def _matches(self, edge: Edge, pad: Gst.Pad) -> bool:
        if edge.source_pad == pad.get_name():
            return True
        template = pad.get_pad_template()
        if template is not None and template.name_template == edge.source_pad:
            return True
        return bool(template_regex(edge.source_pad).match(pad.get_name()))

    def _on_pad_added(self, _element: Gst.Element, pad: Gst.Pad, node_id: str) -> None:
        if pad.get_direction() != Gst.PadDirection.SRC:
            return
        source = self._node(node_id)
        refusals = []
        for edge in list(self._pending.get(node_id, [])):
            if not self._matches(edge, pad):
                continue
            sink_pad = self._sink_pad(edge)
            if sink_pad is None or sink_pad.is_linked():
                continue
            if not pad.can_link(sink_pad):
                refusals.append(self._refusal(edge, pad, sink_pad))
                continue
            if self._link(edge, pad) is None:
                self._pending[node_id].remove(edge)
                target = self._node(edge.target)
                self._emit(
                    {
                        "type": "bus",
                        "kind": "info",
                        "source": source.name,
                        "node_id": self._prefix + node_id,
                        "text": f"Linked dynamic pad {pad.get_name()} → {target.name}.{edge.target_pad}",
                    }
                )
                return
        caps = pad.get_current_caps() or pad.query_caps(None)
        text = f"Dynamic pad {pad.get_name()} ({caps.to_string()[:120]}) matches no free link"
        if refusals:
            text = f"Dynamic pad {pad.get_name()} cannot be linked: {'; '.join(refusals)}"
        self._emit(
            {
                "type": "bus",
                "kind": "warning",
                "source": source.name,
                "node_id": self._prefix + node_id,
                "text": text,
            }
        )

    def _refusal(self, edge: Edge, pad: Gst.Pad, sink_pad: Gst.Pad) -> str:
        """Why the caps of a new dynamic pad do not fit the pad it should link to."""
        caps = pad.get_current_caps() or pad.query_caps(None)
        target = self._node(edge.target)
        return f"{target.name}.{sink_pad.get_name()} refuses it ({mismatch(caps, sink_pad.query_caps(None))})"

    def _on_no_more_pads(self, _element: Gst.Element, node_id: str) -> None:
        for edge in self._pending.get(node_id, []):
            target = self._node(edge.target)
            self._emit(
                {
                    "type": "bus",
                    "kind": "warning",
                    "source": self._node(node_id).name,
                    "node_id": self._prefix + node_id,
                    "text": f"No pad appeared for the link to {target.name}.{edge.target_pad}",
                }
            )
