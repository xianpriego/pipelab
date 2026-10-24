"""Picks concrete pads for links written without pad names (``a ! b``, ``d. ! q``)."""

from __future__ import annotations

from collections import deque

from pipelab.catalog.models import PadTemplateInfo
from pipelab.catalog.store import Catalog, is_template_name
from pipelab.graph.caps_flow import CapsFlow
from pipelab.graph.models import Graph, Node
from pipelab.graph.pads import next_request_pad, used_pads
from pipelab.gst import Gst

_PRESENCE_ORDER = {"always": 0, "request": 1, "sometimes": 2}
_KINDS = {"video", "audio", "text", "subtitle"}
_MAX_DEPTH = 8


def caps_kind(caps: Gst.Caps) -> str | None:
    """Top-level media kind (``video``, ``audio``…) shared by every structure."""
    if caps.is_any() or caps.is_empty():
        return None
    kinds = {caps.get_structure(i).get_name().split("/")[0] for i in range(caps.get_size())}
    return kinds.pop() if len(kinds) == 1 else None


def name_kind(pad_name: str) -> str | None:
    prefix = pad_name.split("_")[0].split("%")[0]
    return prefix if prefix in _KINDS else None


def kind_matches(kind: str, template_name: str) -> bool:
    prefix = name_kind(template_name)
    return prefix == kind or {prefix, kind} == {"text", "subtitle"}


class PadResolver:
    """Resolves pads link by link, so earlier links inform later choices."""

    def __init__(self, catalog: Catalog, graph: Graph, links: list[tuple[str, str]]) -> None:
        self.catalog = catalog
        self.graph = graph
        self.successors: dict[str, list[str]] = {}
        for source, target in links:
            self.successors.setdefault(source, []).append(target)

    def resolve(
        self, source_id: str, source_pad: str | None, target_id: str, target_pad: str | None
    ) -> tuple[str, str] | None:
        source, target = self.graph.node(source_id), self.graph.node(target_id)
        flow = CapsFlow(self.graph, self.catalog)
        if source_pad is None:
            source_pad = self._pick_source(source, target, target_pad, flow)
        else:
            source_pad = self._explicit(source, source_pad, "src")
        if source_pad is None:
            return None
        if target_pad is None:
            target_pad = self._pick_sink(source, source_pad, target, flow)
        else:
            target_pad = self._explicit(target, target_pad, "sink")
        return (source_pad, target_pad) if target_pad is not None else None

    def _concrete(self, node: Node, template: PadTemplateInfo, direction: str) -> str:
        if template.presence == "request":
            return next_request_pad(template.name, used_pads(self.graph, node.id, direction))
        return template.name

    def _explicit(self, node: Node, pad: str, direction: str) -> str:
        template = self.catalog.pad_template(node.factory, pad)
        if template is None:
            return pad
        if template.presence == "request" and is_template_name(pad):
            return self._concrete(node, template, direction)
        return template.name if template.presence == "sometimes" else pad

    def _best(
        self, factory: str, templates: list[PadTemplateInfo], caps: Gst.Caps, kind: str | None
    ) -> PadTemplateInfo | None:
        scored = []
        for index, template in enumerate(templates):
            template_caps = self.catalog.template_caps(factory, template.name)
            specific = not template_caps.is_any() and not caps.is_any()
            if specific and not template_caps.can_intersect(caps):
                continue
            kind_score = 0 if kind and kind_matches(kind, template.name) else 1
            score = (0 if specific else 1, kind_score, _PRESENCE_ORDER[template.presence], index)
            scored.append((score, template))
        return min(scored, key=lambda pair: pair[0])[1] if scored else None

    def _pick(self, node: Node, direction: str, caps: Gst.Caps, kind: str | None) -> str | None:
        templates = self.catalog.templates(node.factory, direction)
        if not templates:
            return None if node.factory in self.catalog else direction
        best = templates[0] if len(templates) == 1 else self._best(node.factory, templates, caps, kind)
        return self._concrete(node, best, direction) if best else None

    def _pick_source(self, source: Node, target: Node, target_pad: str | None, flow: CapsFlow) -> str | None:
        wanted = flow.input_caps(target.id, target_pad) if target_pad else self._accepted(target)
        kind = caps_kind(wanted) or self._downstream_kind(target.id)
        return self._pick(source, "src", wanted, kind)

    def _pick_sink(self, source: Node, source_pad: str, target: Node, flow: CapsFlow) -> str | None:
        offered = flow.output_caps(source.id, source_pad)
        kind = caps_kind(offered) or name_kind(source_pad) or self._upstream_kind(source.id)
        return self._pick(target, "sink", offered, kind)

    def _accepted(self, node: Node) -> Gst.Caps:
        templates = self.catalog.templates(node.factory, "sink")
        caps = Gst.Caps.new_empty()
        for template in templates:
            template_caps = self.catalog.template_caps(node.factory, template.name)
            if template_caps.is_any():
                return template_caps
            caps = caps.merge(template_caps.copy())
        return caps if templates else Gst.Caps.new_any()

    def _downstream_kind(self, node_id: str) -> str | None:
        pending, seen = deque([(node_id, 0)]), {node_id}
        while pending:
            current, depth = pending.popleft()
            kind = caps_kind(self._accepted(self.graph.node(current)))
            if kind or depth >= _MAX_DEPTH:
                return kind
            for successor in self.successors.get(current, []):
                if successor not in seen:
                    seen.add(successor)
                    pending.append((successor, depth + 1))
        return None

    def _upstream_kind(self, node_id: str, depth: int = 0) -> str | None:
        if depth >= _MAX_DEPTH:
            return None
        for edge in self.graph.incoming(node_id):
            kind = name_kind(edge.source_pad) or self._upstream_kind(edge.source, depth + 1)
            if kind:
                return kind
        return None
