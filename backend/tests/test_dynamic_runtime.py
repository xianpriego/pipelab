"""Slots, pipeline functions and no-code probe rules running for real."""

import time

import pytest

from pipelab.graph.dynamic import ApiFunction, FunctionParam
from pipelab.graph.probes import Action, Condition, ProbeRule, ProbeRuleSet, ProbeTarget, Trigger
from tests.api_client import api_client
from tests.dynamic_fixtures import mixer_with_slot, source_component
from tests.helpers import chain
from tests.helpers import graph as graph_of
from tests.runtime_helpers import events_until, import_project, is_playing

pytestmark = pytest.mark.runtime


@pytest.fixture(scope="module")
def client(catalog, tmp_path_factory):
    with api_client(tmp_path_factory.mktemp("dynamic")) as client:
        client.put("/api/components/test-source", json=source_component().model_dump(mode="json"))
        yield client


def _start(client, graph):
    project_id = client.post("/api/projects", json={"name": "dyn", "graph": graph}).json()["id"]
    base = f"/api/projects/{project_id}/runtime"
    client.post(f"{base}/start", json={})
    return base


def _call(client, base, function, **args):
    answer = client.post(f"{base}/call", json={"function": function, "args": args}).json()
    assert answer["ok"], answer
    return answer.get("result")


def _instances(event):
    return event["type"] == "instances"


def test_slot_instances_are_added_and_removed_while_running(client):
    project = client.post(
        "/api/projects", json={"name": "slots", "graph": mixer_with_slot().model_dump()}
    ).json()
    base = f"/api/projects/{project['id']}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events_until(ws, is_playing)
        assert [i["id"] for i in _call(client, base, "list_sources")] == ["source0"]
        assert _call(client, base, "add_source", pattern="snow") == "source1"
        assert _call(client, base, "add_source") == "source2"
        events, _ = events_until(ws, lambda e: _instances(e) and len(e["instances"]) == 3)
        time.sleep(1.5)
        stats, _ = events_until(ws, lambda e: e["type"] == "stats")
        assert stats[-1]["edges"]["s1.source2:src"]["fps"] > 10
        _call(client, base, "remove_source", id="source1")
        events_until(
            ws, lambda e: _instances(e) and [i["id"] for i in e["instances"]] == ["source0", "source2"]
        )
        _call(client, base, "restart_source", id="source0")
        time.sleep(1.0)
        listing = client.get(f"{base}/instances").json()["slots"]["s1"]
        assert sorted(i["id"] for i in listing) == ["source0", "source2"]
        status = client.get(f"{base}/status").json()
        assert status["state"] == "playing", status
        client.post(f"{base}/stop", json={"mode": "kill"})
    errors = [e for e in events if e["type"] == "bus" and e["kind"] == "error"]
    assert errors == []


def test_watchdog_rule_posts_application_messages(client):
    # One branch stops after 15 buffers while another keeps the pipeline alive.
    graph = graph_of(
        [
            ("dead", "videotestsrc", {"is-live": True, "num-buffers": 15}),
            ("dsink", "fakesink", {"async": False}),
            ("alive", "audiotestsrc", {"is-live": True}),
            ("asink", "fakesink", {"async": False}),
        ],
        [("dead", "src", "dsink", "sink"), ("alive", "src", "asink", "sink")],
    )
    graph.probes = [
        ProbeRuleSet(
            id="wd",
            name="Watchdog",
            target=ProbeTarget(kind="edge", id="e0"),
            rules=[
                ProbeRule(
                    id="r1",
                    when=Trigger(type="idle", ms=400),
                    actions=[
                        Action(
                            type="post-message",
                            name="branch-down",
                            fields={"element": "$node", "idle": "$idle_ms"},
                        ),
                        Action(type="log", message="down after {idle_ms} ms", level="warning"),
                    ],
                )
            ],
        )
    ]
    base = _start(client, graph.model_dump())
    with client.websocket_connect(f"{base}/ws") as ws:
        events, _ = events_until(ws, lambda e: e["type"] == "bus" and e.get("name") == "branch-down")
    message = events[-1]
    assert message["kind"] == "application" and message["fields"]["element"] == "dead"
    assert message["fields"]["idle"] >= 400
    assert any(e["type"] == "probe-log" and "down after" in e["message"] for e in events)
    client.post(f"{base}/stop", json={"mode": "kill"})


def test_keyframe_switch_as_rules(client):
    project_id, graph = import_project(
        client,
        (
            "input-selector name=sel ! fakesink "
            "videotestsrc is-live=true ! x264enc tune=zerolatency key-int-max=300 ! sel.sink_0 "
            "videotestsrc is-live=true pattern=ball ! x264enc tune=zerolatency key-int-max=300 ! sel.sink_1"
        ),
    )
    selector = next(n for n in graph["nodes"] if n["factory"] == "input-selector")
    graph["probes"] = [
        ProbeRuleSet(
            id="ks",
            name="Keyframe switch",
            target=ProbeTarget(kind="node", id=selector["id"]),
            variables={"target": ""},
            rules=[
                ProbeRule(
                    id="r1",
                    when=Trigger(type="property", property="active-pad"),
                    actions=[
                        Action(type="set-variable", name="target", value="$value"),
                        Action(type="request-keyframe", node="sel", pad="$value"),
                        Action(type="log", message="waiting for a keyframe on {target}"),
                    ],
                ),
                ProbeRule(
                    id="r2",
                    when=Trigger(type="buffer"),
                    conditions=[Condition(type="keyframe"), Condition(type="pad", op="==", value="$target")],
                    actions=[
                        Action(type="set-property", node="sel", property="active-pad", value="$target"),
                        Action(type="log", message="switched to {target}"),
                        Action(type="set-variable", name="target", value=""),
                    ],
                ),
            ],
        ).model_dump()
    ]
    client.put(f"/api/projects/{project_id}", json={"graph": graph})
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events_until(ws, lambda e: e["type"] == "property" and e.get("value") == "sink_0")
        time.sleep(1.0)
        change = {"node_id": selector["id"], "property": "active-pad", "value": "sink_1"}
        assert client.post(f"{base}/property", json=change).json()["deferred"] is True
        events_until(
            ws, lambda e: e["type"] == "probe-log" and e["message"] == "switched to sink_1", timeout=5
        )
        events_until(
            ws, lambda e: e["type"] == "property" and e.get("origin") == "runtime" and e["value"] == "sink_1"
        )
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_custom_function_and_signal_rules(client):
    graph = chain(("videotestsrc", {"is-live": True}), "identity", "fakesink")
    graph.functions = [
        ApiFunction(
            name="set_pattern",
            params=[FunctionParam(name="pattern", default="ball")],
            actions=[
                Action(type="set-property", node="videotestsrc0", property="pattern", value="$pattern"),
                Action(type="post-message", name="pattern-changed", fields={"pattern": "$pattern"}),
            ],
        )
    ]
    graph.probes = [
        ProbeRuleSet(
            id="gate",
            name="Gate",
            target=ProbeTarget(kind="edge", id="e0"),
            variables={"open": True},
            rules=[
                ProbeRule(
                    id="close",
                    when=Trigger(type="signal", name="close"),
                    actions=[Action(type="set-variable", name="open", value=False)],
                ),
                ProbeRule(
                    id="drop",
                    when=Trigger(type="buffer"),
                    conditions=[Condition(type="variable", name="open", op="==", value=False)],
                    actions=[Action(type="drop")],
                ),
            ],
        )
    ]
    project_id = client.post("/api/projects", json={"name": "fn", "graph": graph.model_dump()}).json()["id"]
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events_until(ws, is_playing)
        _call(client, base, "set_pattern", pattern="snow")
        events_until(ws, lambda e: e["type"] == "bus" and e.get("name") == "pattern-changed")
        assert client.get(f"{base}/properties/n0").json()["properties"]["pattern"] == "snow"
        assert client.post(f"{base}/signal", json={"probe": "gate", "name": "close"}).json() == {"ok": True}
        events_until(ws, lambda e: e["type"] == "stats")
        events, _ = events_until(ws, lambda e: e["type"] == "stats")
        assert events[-1]["edges"]["e1"]["fps"] == 0
        assert not client.post(f"{base}/call", json={"function": "nope", "args": {}}).json()["ok"]
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_export_endpoint_includes_components(client):
    graph = mixer_with_slot().model_dump()
    for language, marker in (("python", "def add_source("), ("rust", "pub fn add_source(")):
        exported = client.post("/api/export", json={"graph": graph, "format": language, "name": "mixer"})
        assert exported.status_code == 200, exported.text
        assert marker in exported.json()["content"]
