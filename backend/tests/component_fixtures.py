"""Components shared by the component tests."""

from __future__ import annotations

from pipelab.components.models import Component, ComponentParam, ComponentPort, ParamTarget
from pipelab.graph.models import Edge, Graph, Node


def source_component() -> Component:
    """``videotestsrc ! capsfilter`` exposing ``src`` and a ``pattern`` parameter."""
    graph = Graph(
        nodes=[
            Node(id="s", factory="videotestsrc", name="src", properties={"is-live": True}),
            Node(
                id="c",
                factory="capsfilter",
                name="caps",
                properties={"caps": "video/x-raw,width=320,height=240,framerate=30/1"},
            ),
        ],
        edges=[Edge(id="e1", source="s", source_pad="src", target="c", target_pad="sink")],
    )
    return Component(
        id="test-source",
        name="Test source",
        graph=graph,
        ports=[ComponentPort(name="src", direction="src", node_id="c", pad="src")],
        parameters=[ComponentParam(name="pattern", targets=[ParamTarget(node_id="s", property="pattern")])],
    )
