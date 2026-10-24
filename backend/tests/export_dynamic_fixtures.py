"""Graphs exercising the dynamic export scenarios (watchdog, slots, functions, keyframe switch)."""

from __future__ import annotations

from pipelab.components.models import Component, ComponentParam, ComponentPort, ParamTarget
from pipelab.graph.dynamic import ApiFunction, FunctionParam, Slot, SlotInstance, SlotLink
from pipelab.graph.models import Edge, Graph, Node
from pipelab.graph.probes import (
    Action,
    Condition,
    ProbeRule,
    ProbeRuleSet,
    ProbeTarget,
    Trigger,
)

Program = tuple[Graph, dict[str, Component]]


def _watchdog(edge_id: str) -> ProbeRuleSet:
    """Posts "branch-down" with the instance name after 500 ms without buffers."""
    return ProbeRuleSet(
        id="watchdog",
        name="watchdog",
        target=ProbeTarget(kind="edge", id=edge_id),
        rules=[
            ProbeRule(
                id="down",
                when=Trigger(type="idle", ms=500),
                actions=[
                    Action(
                        type="post-message",
                        name="branch-down",
                        fields={"input": "$instance", "idle_ms": "$idle_ms"},
                    )
                ],
            )
        ],
    )


def _test_source(cid: str, name: str, size: str, buffers: int | None) -> Component:
    """``videotestsrc ! capsfilter`` with a watchdog on the inner link."""
    graph = Graph(
        nodes=[
            Node(id="s", factory="videotestsrc", name="src", properties={"is-live": True}),
            Node(
                id="c",
                factory="capsfilter",
                name="caps",
                properties={"caps": f"video/x-raw,{size},framerate=30/1"},
            ),
        ],
        edges=[Edge(id="e1", source="s", source_pad="src", target="c", target_pad="sink")],
        probes=[_watchdog("e1")],
    )
    parameters = [ComponentParam(name="pattern", targets=[ParamTarget(node_id="s", property="pattern")])]
    if buffers is not None:
        parameters.append(
            ComponentParam(
                name="buffers",
                default=buffers,
                targets=[ParamTarget(node_id="s", property="num-buffers")],
            )
        )
    return Component(
        id=cid,
        name=name,
        graph=graph,
        ports=[ComponentPort(name="video", direction="src", node_id="c", pad="src")],
        parameters=parameters,
    )


def watchdog_program() -> Program:
    """Scenario 1: an instance whose source stops after 20 buffers."""
    component = _test_source("test-source", "Test Source", "width=320,height=240", 20)
    graph = Graph(
        nodes=[
            Node(id="n1", factory="component:test-source", name="cam", properties={"pattern": "ball"}),
            Node(id="n2", factory="fakesink", name="sink"),
        ],
        edges=[Edge(id="e1", source="n1", source_pad="video", target="n2", target_pad="sink")],
    )
    return graph, {component.id: component}


def slot_program() -> Program:
    """Scenario 2: a slot of test tiles on compositor request pads."""
    component = _test_source("test-tile", "Test Tile", "width=160,height=120", None)
    graph = Graph(
        nodes=[
            Node(id="m", factory="compositor", name="mix"),
            Node(id="k", factory="fakesink", name="sink"),
        ],
        edges=[Edge(id="e1", source="m", source_pad="src", target="k", target_pad="sink")],
        slots=[
            Slot(
                id="tiles",
                name="tiles",
                item="tile",
                component="test-tile",
                links=[SlotLink(port="video", node_id="m", pad="sink_%u", pad_properties={"xpos": "$index"})],
                initial=[SlotInstance(id="tile0", params={"pattern": "ball"})],
            )
        ],
    )
    return graph, {component.id: component}


def function_program() -> Program:
    """Scenario 3: an API function setting a property and posting a message."""
    graph = Graph(
        nodes=[
            Node(id="s", factory="videotestsrc", name="src", properties={"is-live": True}),
            Node(id="k", factory="fakesink", name="sink"),
        ],
        edges=[Edge(id="e1", source="s", source_pad="src", target="k", target_pad="sink")],
        functions=[
            ApiFunction(
                name="configure",
                description="Change the test pattern and tell the application.",
                params=[FunctionParam(name="pattern", default="ball")],
                actions=[
                    Action(type="set-property", node="src", property="pattern", value="$pattern"),
                    Action(type="post-message", name="configured", fields={"pattern": "$pattern"}),
                ],
            )
        ],
    )
    return graph, {}


def keyframe_switch_program() -> Program:
    """Scenario 4: input-selector switching on the next keyframe of the requested input."""
    nodes = [
        Node(id="s0", factory="videotestsrc", name="src0", properties={"is-live": True, "pattern": "smpte"}),
        Node(id="s1", factory="videotestsrc", name="src1", properties={"is-live": True, "pattern": "ball"}),
        Node(id="x0", factory="x264enc", name="enc0", properties={"key-int-max": 300, "tune": "zerolatency"}),
        Node(id="x1", factory="x264enc", name="enc1", properties={"key-int-max": 300, "tune": "zerolatency"}),
        Node(id="sel", factory="input-selector", name="sel"),
        Node(id="k", factory="fakesink", name="sink"),
    ]
    edges = [
        Edge(id="e1", source="s0", source_pad="src", target="x0", target_pad="sink"),
        Edge(id="e2", source="s1", source_pad="src", target="x1", target_pad="sink"),
        Edge(id="e3", source="x0", source_pad="src", target="sel", target_pad="sink_0"),
        Edge(id="e4", source="x1", source_pad="src", target="sel", target_pad="sink_1"),
        Edge(id="e5", source="sel", source_pad="src", target="k", target_pad="sink"),
    ]
    switch = ProbeRuleSet(
        id="switch",
        name="keyframe switch",
        target=ProbeTarget(kind="node", id="sel"),
        variables={"target": ""},
        rules=[
            ProbeRule(
                id="request",
                when=Trigger(type="property", property="active-pad"),
                actions=[
                    Action(type="set-variable", name="target", value="$value"),
                    Action(type="request-keyframe", pad="$value"),
                    Action(type="log", message="switch to {target} requested"),
                ],
            ),
            ProbeRule(
                id="apply",
                when=Trigger(type="buffer"),
                conditions=[
                    Condition(type="keyframe"),
                    Condition(type="pad", op="==", value="$target"),
                ],
                actions=[
                    Action(type="set-property", node="sel", property="active-pad", value="$target"),
                    Action(type="set-variable", name="target", value=""),
                    Action(type="post-message", name="switched", fields={"pad": "$pad"}),
                ],
            ),
        ],
    )
    return Graph(nodes=nodes, edges=edges, probes=[switch]), {}


def sink_slot_program() -> Program:
    """Consumers on tee request pads: removing one drains it (EOS forwarded by the pipeline)."""
    consumer = Component(
        id="test-consumer",
        name="Test Consumer",
        graph=Graph(
            nodes=[
                Node(id="q", factory="queue", name="queue"),
                Node(id="k", factory="fakesink", name="sink", properties={"sync": False}),
            ],
            edges=[Edge(id="e1", source="q", source_pad="src", target="k", target_pad="sink")],
        ),
        ports=[ComponentPort(name="input", direction="sink", node_id="q", pad="sink")],
    )
    graph = Graph(
        nodes=[
            Node(id="s", factory="videotestsrc", name="src", properties={"is-live": True}),
            Node(id="t", factory="tee", name="split", properties={"allow-not-linked": True}),
        ],
        edges=[Edge(id="e1", source="s", source_pad="src", target="t", target_pad="sink")],
        slots=[
            Slot(
                id="outputs",
                name="outputs",
                item="output",
                component="test-consumer",
                links=[SlotLink(port="input", node_id="t", pad="src_%u")],
                initial=[SlotInstance(id="output0")],
            )
        ],
    )
    return graph, {consumer.id: consumer}


def _every_rule() -> list[ProbeRule]:
    """One rule per trigger; together they use every condition and action type."""
    conditions = [
        Condition(type="keyframe"),
        Condition(type="flag", flag="discont", negate=True),
        Condition(type="size", op=">", value=0),
        Condition(type="pts-gap", op="<", value=1000),
        Condition(type="pts-backwards", negate=True),
        Condition(type="every", n=10),
        Condition(type="rate", op=">=", value=1),
        Condition(type="caps-field", field="width", op="==", value=320),
        Condition(type="variable", name="count", op="<", value=1000),
        Condition(type="pad", op="!=", value="$$literal"),
        Condition(type="random", percent=50),
    ]
    post = Action(type="post-message", name="seen", fields={"pts": "$pts", "size": "$size", "time": "$time"})
    return [
        ProbeRule(id="hello", when=Trigger(type="start"), actions=[Action(type="log", message="{node} up")]),
        ProbeRule(
            id="count",
            when=Trigger(type="buffer"),
            conditions=conditions,
            actions=[Action(type="increment", name="count", by=1), post, Action(type="pass")],
        ),
        ProbeRule(id="thin", when=Trigger(type="buffer"), actions=[Action(type="drop")]),
        ProbeRule(
            id="eos",
            when=Trigger(type="event", event="eos"),
            actions=[Action(type="send-event", event="custom", name="bye", fields={"n": "$count"})],
        ),
        ProbeRule(id="any", when=Trigger(type="event", event="any"), actions=[Action(type="block")]),
        ProbeRule(
            id="stall",
            when=Trigger(type="idle", ms=300),
            actions=[
                Action(type="request-keyframe"),
                Action(type="add-instance", slot="extras", params={"pattern": "snow"}),
            ],
        ),
        ProbeRule(id="back", when=Trigger(type="resumed"), actions=[Action(type="unblock")]),
        ProbeRule(
            id="tick",
            when=Trigger(type="interval", ms=1000),
            actions=[
                Action(type="call", function="everything", args={"label": "$label", "count": 2}),
                Action(type="remove-instance", slot="extras", instance="extra1"),
                Action(type="restart-instance", slot="extras", instance="$value"),
            ],
        ),
        ProbeRule(
            id="xpos",
            when=Trigger(type="property", property="xpos"),
            actions=[Action(type="set-variable", name="label", value="$value"), Action(type="pass")],
        ),
        ProbeRule(
            id="poke",
            when=Trigger(type="signal", name="poke"),
            actions=[
                Action(type="set-property", node="mix", property="background", value="black"),
                Action(type="signal", probe="other", name="relay", value=1.5),
                Action(type="signal", name="poke-back"),
                Action(type="remove-probe"),
            ],
        ),
        ProbeRule(id="all", when=Trigger(type="signal"), actions=[Action(type="drop")]),
    ]


def kitchen_sink_program() -> Program:
    """Every trigger, condition and action; nested components, sometimes pads, pad properties."""
    inner = _test_source("inner-src", "Inner Source", "width=320,height=240", None)
    inner.parameters.append(
        ComponentParam(name="live", default=True, targets=[ParamTarget(node_id="s", property="is-live")])
    )
    wrapped = Component(
        id="wrapped",
        name="Wrapped",
        graph=Graph(
            nodes=[
                Node(id="i", factory="component:inner-src", name="inner", properties={"pattern": "ball"}),
                Node(id="q", factory="queue", name="queue"),
            ],
            edges=[Edge(id="e1", source="i", source_pad="video", target="q", target_pad="sink")],
            probes=[
                ProbeRuleSet(
                    id="quiet",
                    name="quiet",
                    target=ProbeTarget(kind="node", id="q"),
                    rules=[ProbeRule(id="r", when=Trigger(type="buffer"), actions=[Action(type="drop")])],
                )
            ],
        ),
        ports=[ComponentPort(name="video", direction="src", node_id="q", pad="src")],
        parameters=[
            ComponentParam(name="pattern", targets=[ParamTarget(node_id="i", property="pattern")]),
            ComponentParam(name="leaky", default="no", targets=[ParamTarget(node_id="q", property="leaky")]),
        ],
    )
    graph = Graph(
        nodes=[
            Node(id="c", factory="component:wrapped", name="cam", properties={"pattern": "smpte"}),
            Node(id="m", factory="compositor", name="mix", pad_properties={"sink_0": {"alpha": 0.5}}),
            Node(id="k", factory="fakesink", name="sink"),
            Node(id="f", factory="filesrc", name="file", properties={"location": "/nonexistent.mp4"}),
            Node(id="d", factory="decodebin", name="decode"),
            Node(id="v", factory="videoconvert", name="convert"),
            Node(id="k2", factory="fakesink", name="sink2"),
        ],
        edges=[
            Edge(id="e1", source="c", source_pad="video", target="m", target_pad="sink_0"),
            Edge(id="e2", source="m", source_pad="src", target="k", target_pad="sink"),
            Edge(id="e3", source="f", source_pad="src", target="d", target_pad="sink"),
            Edge(id="e4", source="d", source_pad="src_%u", target="v", target_pad="sink"),
            Edge(id="e5", source="v", source_pad="src", target="k2", target_pad="sink"),
        ],
        probes=[
            ProbeRuleSet(
                id="all",
                name="everything",
                target=ProbeTarget(kind="node", id="m", pad="sink_%u"),
                variables={"count": 0, "label": "a", "ratio": 1.5, "flag": True},
                rules=_every_rule(),
            ),
            ProbeRuleSet(
                id="other",
                name="other",
                target=ProbeTarget(kind="edge", id="e1"),
                rules=[
                    ProbeRule(
                        id="relay",
                        when=Trigger(type="signal", name="relay"),
                        actions=[Action(type="log", message="relayed {value}", level="warning")],
                    )
                ],
            ),
        ],
        slots=[
            Slot(
                id="s-extras",
                name="extras",
                item="extra",
                component="inner-src",
                links=[
                    SlotLink(
                        port="video",
                        node_id="m",
                        pad="sink_%u",
                        pad_properties={"xpos": "$index", "ypos": 10, "alpha": 0.8},
                    )
                ],
                initial=[SlotInstance(id="extra0", params={"pattern": "snow", "live": True})],
                max_instances=4,
            )
        ],
        functions=[
            ApiFunction(
                name="everything",
                description="Uses every action that applies to functions.",
                params=[
                    FunctionParam(name="label", default="x"),
                    FunctionParam(name="count", type="int", default=3),
                    FunctionParam(name="ratio", type="float", default=0.5),
                    FunctionParam(name="on", type="bool", default=True),
                    FunctionParam(name="unused", type="int"),
                ],
                actions=[
                    Action(type="set-property", node="mix", property="background", value="$label"),
                    Action(type="set-property", node="mix", pad="sink_0", property="alpha", value="$ratio"),
                    Action(
                        type="post-message",
                        name="done",
                        fields={"count": "$count", "on": "$on", "t": "$time"},
                    ),
                    Action(
                        type="send-event", node="mix", event="custom", direction="upstream", fields={"a": 1}
                    ),
                    Action(type="request-keyframe", node="mix", pad="sink_0"),
                    Action(type="log", message="label {label}", level="error"),
                    Action(type="signal", probe="all", name="poke", value="$count"),
                    Action(type="call", function="noop"),
                    Action(type="add-instance", slot="extras", params={"pattern": "$label"}),
                    Action(type="remove-instance", slot="s-extras", instance="extra0"),
                    Action(type="restart-instance", slot="extras", instance="extra1"),
                    Action(type="block"),
                ],
            ),
            ApiFunction(name="noop"),
        ],
    )
    return graph, {c.id: c for c in (inner, wrapped)}
