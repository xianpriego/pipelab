"""Decides whether a link between two pads is valid and how to improve it."""

from __future__ import annotations

from pipelab.catalog.models import ElementInfo
from pipelab.graph.analyzer import Analyzer
from pipelab.graph.bridge import media_names
from pipelab.graph.caps_flow import caps_to_string
from pipelab.graph.models import Edge, Fix, Graph, Issue, LinkCheckResult, Node, PadRef, Suggestion
from pipelab.graph.pads import resolve_pad_name
from pipelab.graph.suggest import insert_suggestion
from pipelab.graph.topology import reaches
from pipelab.gst import Gst
from pipelab.gst.caps import media_types

RAW_CONVERTERS = {"video/x-raw": ["videoconvert"], "audio/x-raw": ["audioconvert", "audioresample"]}
CONVERTER_NAMES = {
    "videoconvert",
    "videoconvertscale",
    "videoscale",
    "videorate",
    "audioconvert",
    "audioresample",
    "audiorate",
    "capsfilter",
}
_SEVERITY_ORDER = {"ok": 0, "info": 1, "warning": 2, "error": 3}


def describe_caps(caps: Gst.Caps) -> str:
    names = media_types(caps)
    return ", ".join(names[:4]) + (" …" if len(names) > 4 else "")


class _LinkContext:
    def __init__(self, analyzer: Analyzer, graph: Graph, edge: Edge) -> None:
        self.analyzer = analyzer
        self.graph = graph
        self.edge = edge
        self.existing = graph.edge(edge.id) is not None
        self.issues: list[Issue] = []
        self.src_presence = "always"
        self.sink_presence = "always"

    def add(
        self, rule: str, severity: str, message: str, suggestions: list[Suggestion] | None = None
    ) -> None:
        self.issues.append(
            Issue(
                id=f"{rule}:{self.edge.id}",
                rule=rule,
                severity=severity,
                message=message,
                node_ids=[self.edge.source, self.edge.target],
                edge_ids=[self.edge.id] if self.existing else [],
                suggestions=suggestions or [],
            )
        )

    def result(self, src: Gst.Caps | None = None, sink: Gst.Caps | None = None) -> LinkCheckResult:
        severity = max((i.severity for i in self.issues), key=_SEVERITY_ORDER.get, default="ok")
        common = src.intersect(sink) if src is not None and sink is not None else None
        return LinkCheckResult(
            allowed=severity != "error",
            severity=severity,
            edge=self.edge,
            source_caps=caps_to_string(src) if src is not None else "",
            target_caps=caps_to_string(sink) if sink is not None else "",
            common_caps=caps_to_string(common) if common is not None and not common.is_empty() else None,
            issues=self.issues,
        )


def check_link(analyzer: Analyzer, graph: Graph, edge: Edge) -> LinkCheckResult:
    ctx = _LinkContext(analyzer, graph, edge)
    source, target = graph.node(edge.source), graph.node(edge.target)
    if source is None or target is None:
        ctx.add("unknown-node", "error", "The link references an element that does not exist.")
        return ctx.result()
    if source.id == target.id:
        ctx.add("self-link", "error", "An element cannot be linked to itself.")
        return ctx.result()
    if not _resolve_pads(ctx, source, target):
        return ctx.result()
    if not _check_pad_usage(ctx, source, target) or not _check_cycle(ctx):
        return ctx.result()
    return _check_caps(ctx, source, target)


def _resolve_pads(ctx: _LinkContext, source: Node, target: Node) -> bool:
    catalog = ctx.analyzer.catalog
    for node in (source, target):
        if node.factory not in catalog:
            ctx.add("missing-element", "error", f"Element '{node.factory}' is not installed.")
            return False
    src_pad, src_template = resolve_pad_name(
        catalog, ctx.graph, source, ctx.edge.source_pad, "src", ctx.edge.id
    )
    sink_pad, sink_template = resolve_pad_name(
        catalog, ctx.graph, target, ctx.edge.target_pad, "sink", ctx.edge.id
    )
    ctx.edge = ctx.edge.model_copy(update={"source_pad": src_pad, "target_pad": sink_pad})
    if src_template is None or src_template.direction != "src":
        ctx.add("unknown-pad", "error", f"'{source.name}' has no output pad '{ctx.edge.source_pad}'.")
        return False
    if sink_template is None or sink_template.direction != "sink":
        ctx.add("unknown-pad", "error", f"'{target.name}' has no input pad '{ctx.edge.target_pad}'.")
        return False
    ctx.src_presence, ctx.sink_presence = src_template.presence, sink_template.presence
    return True


def _other_edges(ctx: _LinkContext) -> list[Edge]:
    return [e for e in ctx.graph.edges if e.id != ctx.edge.id]


def _check_pad_usage(ctx: _LinkContext, source: Node, target: Node) -> bool:
    edge = ctx.edge
    if ctx.src_presence != "sometimes":
        taken = next(
            (e for e in _other_edges(ctx) if e.source == source.id and e.source_pad == edge.source_pad), None
        )
        if taken is not None:
            fix = Fix(
                kind="insert_tee",
                edge_ids=[taken.id],
                source=PadRef(node_id=source.id, pad=edge.source_pad),
                target=PadRef(node_id=target.id, pad=edge.target_pad),
            )
            ctx.add(
                "pad-in-use",
                "error",
                f"Pad {source.name}.{edge.source_pad} is already linked. A pad has a single peer: "
                "split the stream with a tee (and a queue per branch).",
                [Suggestion(title="Insert tee with a queue per branch", fix=fix)],
            )
            return False
    taken_sink = any(e.target == target.id and e.target_pad == edge.target_pad for e in _other_edges(ctx))
    if taken_sink:
        ctx.add(
            "pad-in-use",
            "error",
            f"Pad {target.name}.{edge.target_pad} is already linked. Use a mixer (compositor, "
            "audiomixer), a muxer or an input-selector/funnel to merge streams.",
        )
        return False
    return True


def _check_cycle(ctx: _LinkContext) -> bool:
    if reaches(ctx.graph, ctx.edge.target, ctx.edge.source, skip_edge=ctx.edge.id):
        ctx.add("cycle", "error", "This link would create a loop; GStreamer pipelines are acyclic.")
        return False
    return True


def _check_caps(ctx: _LinkContext, source: Node, target: Node) -> LinkCheckResult:
    flow = ctx.analyzer.flow(ctx.graph)
    src = flow.output_caps(source.id, ctx.edge.source_pad)
    sink = flow.input_caps(target.id, ctx.edge.target_pad)
    if src.is_any() or sink.is_any():
        return ctx.result(src, sink)
    if not src.can_intersect(sink):
        _incompatible(ctx, source, target, src, sink)
        return ctx.result(src, sink)
    source_info = ctx.analyzer.element(source)
    target_info = ctx.analyzer.element(target)
    _safety_converter(ctx, source_info, target_info, src, sink)
    _missing_parser(ctx, source_info, target_info, src, sink)
    return ctx.result(src, sink)


def _incompatible(ctx: _LinkContext, source: Node, target: Node, src: Gst.Caps, sink: Gst.Caps) -> None:
    chains = ctx.analyzer.bridges.find(src, sink)
    suggestions = [
        insert_suggestion(ctx.edge, chain, ctx.existing, "Converts between both formats.") for chain in chains
    ]
    hint = " Insert one of the suggested elements." if chains else " No converter was found in the catalog."
    ctx.add(
        "caps-incompatible",
        "error",
        f"{source.name} produces {describe_caps(src)} but {target.name}.{ctx.edge.target_pad} "
        f"accepts {describe_caps(sink)}.{hint}",
        suggestions,
    )


def _safety_converter(
    ctx: _LinkContext, source: ElementInfo | None, target: ElementInfo | None, src: Gst.Caps, sink: Gst.Caps
) -> None:
    if source is None or target is None or src.is_subset(sink):
        return
    if source.name in CONVERTER_NAMES or target.name in CONVERTER_NAMES:
        return
    raw = media_names(src) & media_names(sink) & set(RAW_CONVERTERS)
    if not raw:
        return
    factories = RAW_CONVERTERS[sorted(raw)[0]]
    ctx.add(
        "safety-converter",
        "info",
        f"{source.name} can produce formats that {target.name} does not accept; negotiation "
        f"depends on what is picked at runtime. A {' ! '.join(factories)} makes it robust.",
        [insert_suggestion(ctx.edge, factories, ctx.existing, "Adapts format, layout and rate when needed.")],
    )


def _requires_parsed(caps: Gst.Caps) -> bool:
    for index in range(caps.get_size()):
        structure = caps.get_structure(index)
        if structure.has_field("parsed") and structure.get_value("parsed") is True:
            return True
    return False


def _missing_parser(
    ctx: _LinkContext, source: ElementInfo | None, target: ElementInfo | None, src: Gst.Caps, sink: Gst.Caps
) -> None:
    if source is None or target is None or "parser" in source.categories:
        return
    if not {"decoder", "muxer", "payloader"} & set(target.categories):
        return
    if media_names(src) & {"video/x-raw", "audio/x-raw", "ANY"}:
        return
    if "parser" in target.categories:
        return
    parsers = ctx.analyzer.bridges.find_parsers(src, sink)
    if not parsers:
        return
    strict = _requires_parsed(sink) or bool({"depayloader", "demuxer", "source"} & set(source.categories))
    ctx.add(
        "missing-parser",
        "warning" if strict else "info",
        f"Put a parser ({parsers[0]}) between {source.name} and {target.name}: it normalises "
        "stream-format/alignment, fills codec_data and timestamps.",
        [
            insert_suggestion(ctx.edge, [p], ctx.existing, "Parses the elementary stream.")
            for p in parsers[:2]
        ],
    )
