"""Caps negotiation best practices."""

from __future__ import annotations

from pipelab.catalog.models import ElementInfo
from pipelab.graph.caps_flow import CAPS_FILTERS, CONVERTERS
from pipelab.graph.models import Edge, Issue, Node
from pipelab.graph.rules.base import RuleContext, issue
from pipelab.graph.suggest import insert_suggestion

DEFAULT_RAW_CAPS = {
    "video/x-raw": "video/x-raw,width=1280,height=720,framerate=30/1",
    "audio/x-raw": "audio/x-raw,rate=48000,channels=2",
}
# Converters adapt formats but do not pin them; a capsfilter after them still counts.
_CONVERTERS = CONVERTERS | {"queue"}


def _raw_media(element: ElementInfo) -> str | None:
    for pad in element.pads:
        if pad.direction == "src":
            for media in pad.media_types:
                if media in DEFAULT_RAW_CAPS:
                    return media
    return None


def _flexible_raw_source(node: Node, element: ElementInfo) -> bool:
    if "source" not in element.categories or "caps" in node.properties:
        return False
    return (
        element.pads and all(p.direction == "src" for p in element.pads) and _raw_media(element) is not None
    )


def _pinned_downstream(ctx: RuleContext, edge: Edge) -> bool:
    """Whether a capsfilter follows ``edge``, possibly after some converters."""
    seen: set[str] = set()
    while edge is not None and edge.target not in seen:
        target = ctx.target(edge)
        if target.factory in CAPS_FILTERS:
            return True
        if target.factory not in _CONVERTERS:
            return False
        seen.add(target.id)
        outgoing = ctx.graph.outgoing(target.id)
        edge = outgoing[0] if len(outgoing) == 1 else None
    return False


def source_caps(ctx: RuleContext) -> list[Issue]:
    issues = []
    for node, element in ctx.nodes_with(_flexible_raw_source):
        media = _raw_media(element)
        for edge in ctx.graph.outgoing(node.id):
            if media is None or _pinned_downstream(ctx, edge):
                continue
            caps = DEFAULT_RAW_CAPS[media]
            issues.append(
                issue(
                    "source-caps",
                    "info",
                    f"{node.name} can produce many formats; a capsfilter after it makes negotiation "
                    "deterministic (resolution, rate, channels) and documents what the pipeline expects.",
                    [node],
                    [edge],
                    [
                        insert_suggestion(
                            edge, ["capsfilter"], True, f"caps={caps}", {"capsfilter": {"caps": caps}}
                        )
                    ],
                )
            )
    return issues
