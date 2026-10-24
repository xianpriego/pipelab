"""Pad name resolution: request pad numbering and automatic pad selection."""

from __future__ import annotations

import re

from pipelab.catalog.models import PadTemplateInfo
from pipelab.catalog.store import Catalog, is_template_name
from pipelab.graph.models import Graph, Node
from pipelab.gst import Gst
from pipelab.gst.caps import parse_caps

_TOKEN = re.compile(r"%[uds]")


def used_pads(graph: Graph, node_id: str, direction: str, exclude_edge: str | None = None) -> set[str]:
    names = set()
    for edge in graph.edges:
        if edge.id == exclude_edge:
            continue
        if direction == "src" and edge.source == node_id:
            names.add(edge.source_pad)
        if direction == "sink" and edge.target == node_id:
            names.add(edge.target_pad)
    return names


def next_request_pad(template_name: str, used: set[str]) -> str:
    """``sink_%u`` → first ``sink_N`` not in ``used``."""
    index = 0
    while True:
        candidate = _TOKEN.sub(str(index), template_name, count=1)
        candidate = _TOKEN.sub("0", candidate)
        if candidate not in used:
            return candidate
        index += 1


def resolve_pad_name(
    catalog: Catalog, graph: Graph, node: Node, pad: str, direction: str, exclude_edge: str | None = None
) -> tuple[str, PadTemplateInfo | None]:
    """Concrete name for a pad the user picked (template handles become new pads)."""
    template = catalog.pad_template(node.factory, pad)
    if template is None or template.direction != direction:
        return pad, template
    if template.presence == "request" and is_template_name(pad):
        return next_request_pad(pad, used_pads(graph, node.id, direction, exclude_edge)), template
    return pad, template


def pick_pad(
    catalog: Catalog, graph: Graph, node: Node, direction: str, peer_caps: Gst.Caps | None = None
) -> str | None:
    """Choose a pad to auto-link ``node`` (used by fixes and the importer).

    Prefers free always pads, then request templates, then sometimes templates,
    picking the first whose template caps are compatible with ``peer_caps``.
    """
    used = used_pads(graph, node.id, direction)
    templates = catalog.templates(node.factory, direction)
    order = {"always": 0, "request": 1, "sometimes": 2}
    for template in sorted(templates, key=lambda t: order[t.presence]):
        if peer_caps is not None and not parse_caps(template.caps).can_intersect(peer_caps):
            continue
        if template.presence == "always":
            if template.name not in used:
                return template.name
        elif template.presence == "request":
            return next_request_pad(template.name, used)
        else:
            return template.name
    return None
