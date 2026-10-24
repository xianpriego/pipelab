"""Probe scripts: recipes, validation and their behaviour in real pipelines."""

import ast
import time

import pytest

from pipelab.graph.models import ProbeScript, ScriptTarget
from pipelab.graph.validate import validate_graph
from pipelab.scripts.catalog import recipes
from tests.api_client import api_client
from tests.helpers import chain
from tests.runtime_helpers import events_until, is_playing

# A 10 s GOP: switching within ~2 s proves the requested keyframe arrived.
TWO_ENCODED_INPUTS = (
    "input-selector name=sel ! fakesink "
    "videotestsrc is-live=true ! x264enc tune=zerolatency key-int-max=300 ! sel.sink_0 "
    "videotestsrc is-live=true pattern=ball ! x264enc tune=zerolatency key-int-max=300 ! sel.sink_1"
)


def _recipe(recipe_id):
    return next(r for r in recipes() if r.id == recipe_id)


def _script(recipe_id, kind, target_id, code=None):
    recipe = _recipe(recipe_id)
    return ProbeScript(
        id=f"s-{recipe_id}",
        name=recipe.name,
        target=ScriptTarget(kind=kind, id=target_id),
        code=code if code is not None else recipe.code,
    )


@pytest.fixture(scope="module")
def client(catalog, tmp_path_factory):
    with api_client(tmp_path_factory.mktemp("scripts")) as client:
        yield client


def _project(client, graph):
    return client.post("/api/projects", json={"name": "scripts", "graph": graph}).json()["id"]


def test_every_recipe_is_valid_python_with_callbacks():
    for recipe in recipes():
        tree = ast.parse(recipe.code)
        assert {n.name for n in tree.body if isinstance(n, ast.FunctionDef)} & {
            "on_buffer",
            "on_event",
            "on_property",
            "setup",
        }, recipe.id
    assert _recipe("keyframe-switch").factories == ["input-selector", "output-selector"]


def test_recipes_endpoint(client):
    listed = {r["id"]: r for r in client.get("/api/scripts/recipes").json()}
    assert listed["gate"]["target_kind"] == "edge" and "def on_trigger" in listed["gate"]["code"]


def test_validation_reports_script_problems(analyzer):
    g = chain("videotestsrc", "fakesink")
    g.scripts = [
        _script("custom-link", "edge", "e0", code="def on_buffer(ctx, pad, buffer)\n    return PASS\n"),
        _script("gate", "edge", "missing"),
        _script("custom-element", "node", "n0", code="x = 1\n"),
    ]
    messages = {i.message for i in validate_graph(analyzer, g) if i.rule == "script"}
    assert any("line 1" in m for m in messages)
    assert any("no longer exists" in m for m in messages)
    assert any("defines none of" in m for m in messages)


def test_keyframe_switch_waits_for_a_requested_keyframe(client):
    graph = client.post("/api/import/gst-launch", json={"description": TWO_ENCODED_INPUTS}).json()["graph"]
    selector = next(n for n in graph["nodes"] if n["factory"] == "input-selector")
    graph["scripts"] = [_script("keyframe-switch", "node", selector["id"]).model_dump()]
    base = f"/api/projects/{_project(client, graph)}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events_until(ws, lambda e: e["type"] == "property" and e.get("value") == "sink_0")
        time.sleep(1.0)  # well inside the 10 s GOP of sink_1
        change = {"node_id": selector["id"], "property": "active-pad", "value": "sink_1"}
        answer = client.post(f"{base}/property", json=change).json()
        assert answer["deferred"] is True and answer["value"] == "sink_0"
        requested = time.monotonic()
        events, _ = events_until(ws, lambda e: e["type"] == "script" and "switched to sink_1" in e["message"])
        assert time.monotonic() - requested < 3.0
        assert any(e["type"] == "script" and "waiting for a keyframe" in e["message"] for e in events)
        events_until(
            ws, lambda e: e["type"] == "property" and e.get("origin") == "runtime" and e["value"] == "sink_1"
        )
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_gate_closes_and_reopens_a_link(client):
    graph = chain(
        ("videotestsrc", {"is-live": True}),
        ("x264enc", {"tune": "zerolatency", "key-int-max": 300}),
        "identity",
        "fakesink",
    ).model_dump()
    graph["scripts"] = [_script("gate", "edge", "e1").model_dump()]
    base = f"/api/projects/{_project(client, graph)}/runtime"

    def downstream_fps(ws):
        _, _ = events_until(ws, lambda e: e["type"] == "stats")
        events, _ = events_until(ws, lambda e: e["type"] == "stats")
        return events[-1]["edges"]["e2"]["fps"]

    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events_until(ws, is_playing)
        assert downstream_fps(ws) > 10
        assert client.post(f"{base}/trigger", json={"script_id": "s-gate", "value": "close"}).json() == {
            "ok": True
        }
        assert downstream_fps(ws) == 0
        client.post(f"{base}/trigger", json={"script_id": "s-gate", "value": "open"})
        assert downstream_fps(ws) > 10  # reopened quickly thanks to the requested keyframe
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_script_errors_are_reported_without_stopping_the_pipeline(client):
    broken = "def on_buffer(ctx, pad, buffer):\n    return 1 / 0\n"
    graph = chain(("videotestsrc", {"is-live": True}), "fakesink").model_dump()
    graph["scripts"] = [_script("custom-link", "edge", "e0", code=broken).model_dump()]
    base = f"/api/projects/{_project(client, graph)}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events, _ = events_until(ws, lambda e: e["type"] == "script" and e["level"] == "error")
        assert "ZeroDivisionError" in events[-1]["message"] and "line 2" in events[-1]["message"]
        events_until(ws, is_playing)
        answer = client.post(f"{base}/trigger", json={"script_id": "s-custom-link"}).json()
        assert answer["ok"] is False and "on_trigger" in answer["error"]
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_script_syntax_errors_stop_the_build(client):
    graph = chain(("videotestsrc", {"is-live": True}), "fakesink").model_dump()
    graph["scripts"] = [_script("custom-link", "edge", "e0", code="def on_buffer(:\n").model_dump()]
    base = f"/api/projects/{_project(client, graph)}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events, _ = events_until(ws, lambda e: e["type"] == "bus" and e["kind"] == "error")
    assert "SyntaxError" in events[-1]["text"]


def test_keyframe_switch_does_not_switch_on_delta_frames(client):
    graph = client.post("/api/import/gst-launch", json={"description": TWO_ENCODED_INPUTS}).json()["graph"]
    selector = next(n for n in graph["nodes"] if n["factory"] == "input-selector")
    code = _recipe("keyframe-switch").code.replace("REQUEST_KEYFRAME = True", "REQUEST_KEYFRAME = False")
    graph["scripts"] = [_script("keyframe-switch", "node", selector["id"], code=code).model_dump()]
    base = f"/api/projects/{_project(client, graph)}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events_until(ws, lambda e: e["type"] == "property" and e.get("value") == "sink_0")
        time.sleep(1.0)
        change = {"node_id": selector["id"], "property": "active-pad", "value": "sink_1"}
        assert client.post(f"{base}/property", json=change).json()["deferred"] is True
        time.sleep(2.0)  # the next natural keyframe of sink_1 is ~9 s away
        live = client.get(f"{base}/properties/{selector['id']}").json()["properties"]
        assert live["active-pad"] == "sink_0"
        client.post(f"{base}/stop", json={"mode": "kill"})
