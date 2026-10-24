"""Components and graphs shared by the component / dynamic pipeline tests."""

from __future__ import annotations

from pipelab.components.models import Component, ComponentParam, ComponentPort, ParamTarget
from pipelab.graph.dynamic import Slot, SlotInstance, SlotLink
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


def mixer_with_slot(initial: int = 1) -> Graph:
    """compositor ! fakesink with a ``sources`` slot of test sources on compositor.sink_%u."""
    return Graph(
        nodes=[
            Node(id="mix", factory="compositor", name="mix"),
            Node(id="out", factory="fakesink", name="out"),
        ],
        edges=[Edge(id="e1", source="mix", source_pad="src", target="out", target_pad="sink")],
        slots=[
            Slot(
                id="s1",
                name="sources",
                item="source",
                component="test-source",
                links=[SlotLink(port="src", node_id="mix", pad="sink_%u", pad_properties={"xpos": "$index"})],
                initial=[SlotInstance(id=f"source{i}", params={"pattern": "ball"}) for i in range(initial)],
            )
        ],
    )
