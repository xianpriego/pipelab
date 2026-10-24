"""Graph with components shared by the export tests: nested instances, a port on a sometimes pad,
request pads with pad properties and parameters of every kind."""

from __future__ import annotations

from pipelab.components.models import Component, ComponentParam, ComponentPort, ParamTarget
from pipelab.graph.models import Edge, Graph, Node

Program = tuple[Graph, dict[str, Component]]


def _inner_source() -> Component:
    """``videotestsrc ! capsfilter``: pattern (enum), buffers (int, default 30), live (bool)."""
    graph = Graph(
        nodes=[
            Node(id="s", factory="videotestsrc", name="src"),
            Node(
                id="c",
                factory="capsfilter",
                name="caps",
                properties={"caps": "video/x-raw,width=320,height=240"},
            ),
        ],
        edges=[Edge(id="e1", source="s", source_pad="src", target="c", target_pad="sink")],
    )
    return Component(
        id="inner-src",
        name="Inner Source",
        graph=graph,
        ports=[ComponentPort(name="video", direction="src", node_id="c", pad="src")],
        parameters=[
            ComponentParam(name="pattern", targets=[ParamTarget(node_id="s", property="pattern")]),
            ComponentParam(
                name="buffers", default=30, targets=[ParamTarget(node_id="s", property="num-buffers")]
            ),
            ComponentParam(
                name="live", default=False, targets=[ParamTarget(node_id="s", property="is-live")]
            ),
        ],
    )


def _wrapped() -> Component:
    """An instance of inner-src behind a queue: parameters reach the nested instance."""
    graph = Graph(
        nodes=[
            Node(id="i", factory="component:inner-src", name="inner", properties={"pattern": "ball"}),
            Node(id="q", factory="queue", name="queue"),
        ],
        edges=[Edge(id="e1", source="i", source_pad="video", target="q", target_pad="sink")],
    )
    return Component(
        id="wrapped",
        name="Wrapped",
        graph=graph,
        ports=[ComponentPort(name="video", direction="src", node_id="q", pad="src")],
        parameters=[
            ComponentParam(
                name="pattern",
                description="Test pattern of the nested source",
                targets=[ParamTarget(node_id="i", property="pattern")],
            ),
            ComponentParam(name="leaky", default="no", targets=[ParamTarget(node_id="q", property="leaky")]),
        ],
    )


def _decoded() -> Component:
    """Encodes and decodes a test pattern: its port is a *sometimes* pad of decodebin."""
    graph = Graph(
        nodes=[
            Node(id="s", factory="videotestsrc", name="src", properties={"num-buffers": 30}),
            Node(id="e", factory="x264enc", name="enc", properties={"tune": "zerolatency"}),
            Node(id="p", factory="h264parse", name="parse"),
            Node(id="d", factory="decodebin", name="decode"),
        ],
        edges=[
            Edge(id="e1", source="s", source_pad="src", target="e", target_pad="sink"),
            Edge(id="e2", source="e", source_pad="src", target="p", target_pad="sink"),
            Edge(id="e3", source="p", source_pad="src", target="d", target_pad="sink"),
        ],
    )
    return Component(
        id="decoded",
        name="Decoded",
        graph=graph,
        ports=[ComponentPort(name="video", direction="src", node_id="d", pad="src_%u")],
    )


def components_program() -> Program:
    """Two instances on compositor request pads (with pad properties), then a sink; runs to EOS."""
    graph = Graph(
        nodes=[
            Node(id="c", factory="component:wrapped", name="cam", properties={"pattern": "smpte"}),
            Node(id="d", factory="component:decoded", name="dec"),
            Node(
                id="m",
                factory="compositor",
                name="mix",
                pad_properties={"sink_0": {"alpha": 0.5}, "sink_1": {"xpos": 160}},
            ),
            Node(id="v", factory="videoconvert", name="convert"),
            Node(id="k", factory="fakesink", name="sink"),
        ],
        edges=[
            Edge(id="e1", source="c", source_pad="video", target="m", target_pad="sink_0"),
            Edge(id="e2", source="d", source_pad="video", target="v", target_pad="sink"),
            Edge(id="e3", source="v", source_pad="src", target="m", target_pad="sink_1"),
            Edge(id="e4", source="m", source_pad="src", target="k", target_pad="sink"),
        ],
    )
    return graph, {c.id: c for c in (_inner_source(), _wrapped(), _decoded())}
