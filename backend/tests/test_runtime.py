"""End-to-end runtime tests: real pipelines in worker processes."""

import time

import pytest

from pipelab.runtime.protocol import decode_ws_binary
from tests.helpers import chain
from tests.runtime_helpers import create_project, events_until, is_stopped

pytestmark = pytest.mark.runtime


_project = create_project
_events = events_until
_stopped = is_stopped


def test_pipeline_runs_to_eos_with_preview_and_stats(client):
    graph = chain(("videotestsrc", {"num-buffers": 45}), "videoconvert", "autovideosink")
    project_id = _project(client, graph)
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        assert client.post(f"/api/projects/{project_id}/runtime/start", json={}).status_code == 200
        events, previews = _events(ws, _stopped)
    kinds = {(e["type"], e.get("kind") or e.get("state")) for e in events}
    assert ("bus", "eos") in kinds and ("state", "playing") in kinds and ("state", "stopped") in kinds
    assert any(e["type"] == "caps" and e["edge_id"] == "e0" for e in events)
    assert previews and previews[0]["kind"] == "video" and previews[0]["node_id"] == "n2"
    assert client.get(f"/api/projects/{project_id}/runtime/status").json()["state"] == "stopped"


def test_errors_point_to_the_failing_node(client):
    graph = chain(("filesrc", {"location": "/nonexistent.mp4"}), "fakesink")
    project_id = _project(client, graph)
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        client.post(f"/api/projects/{project_id}/runtime/start", json={})
        events, _ = _events(ws, lambda e: e["type"] == "bus" and e["kind"] == "error")
    error = events[-1]
    assert error["node_id"] == "n0" and error["hint"]
    client.post(f"/api/projects/{project_id}/runtime/stop", json={"mode": "kill"})


def test_live_property_changes_and_inspection(client):
    graph = chain(("videotestsrc", {"is-live": True}), "fakesink")
    project_id = _project(client, graph)
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        _events(ws, lambda e: e["type"] == "state" and e["state"] == "playing")
        changed = client.post(
            f"{base}/property", json={"node_id": "n0", "property": "pattern", "value": "ball"}
        )
        assert changed.json() == {**changed.json(), "ok": True, "value": "ball"}
        bad = client.post(f"{base}/property", json={"node_id": "n0", "property": "pattern", "value": "bogus"})
        assert bad.status_code == 422
        values = client.get(f"{base}/properties/n0").json()
        assert values["properties"]["pattern"] == "ball"
        svg = client.get(f"{base}/dot")
        assert svg.headers["content-type"].startswith("image/svg") and b"<svg" in svg.content
        client.post(f"{base}/pause")
        _events(ws, lambda e: e["type"] == "state" and e["state"] == "paused")
        client.post(f"{base}/stop", json={"mode": "eos"})
        _events(ws, _stopped)


def test_input_selector_switches_live(client):
    imported = client.post(
        "/api/import/gst-launch",
        json={
            "description": (
                "input-selector name=sel ! fakesink videotestsrc is-live=true ! sel.sink_0 "
                "videotestsrc is-live=true pattern=ball ! sel.sink_1"
            )
        },
    ).json()["graph"]
    project_id = client.post("/api/projects", json={"name": "sel", "graph": imported}).json()["id"]
    selector = next(n for n in imported["nodes"] if n["factory"] == "input-selector")
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        _events(ws, lambda e: e["type"] == "state" and e["state"] == "playing")
        result = client.post(
            f"{base}/property", json={"node_id": selector["id"], "property": "active-pad", "value": "sink_1"}
        ).json()
        assert result["ok"] and result["value"] == "sink_1"
        client.post(f"{base}/stop", json={"mode": "kill"})


@pytest.mark.parametrize(
    ("chain_specs", "edge", "kind"),
    [
        ((("videotestsrc", {"is-live": True}), "fakesink"), "e0", "video"),
        ((("videotestsrc", {"is-live": True}), "x264enc", "h264parse", "fakesink"), "e2", "video"),
        ((("audiotestsrc", {"is-live": True}), "fakesink"), "e0", "audio"),
        (
            (
                ("videotestsrc", {"is-live": True}),
                ("x264enc", {"tune": "zerolatency", "key-int-max": 15}),
                ("rtph264pay", {"config-interval": -1}),
                "fakesink",
            ),
            "e2",
            "video",
        ),
    ],
)
def test_link_tap_previews_raw_and_encoded_streams(client, chain_specs, edge, kind):
    project_id = _project(client, chain(*chain_specs))
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        _events(ws, lambda e: e["type"] == "caps" and e["edge_id"] == edge)
        assert client.post(f"{base}/tap", json={"edge_id": edge}).json() == {"ok": True}
        deadline, previews = time.monotonic() + 10, []
        while not previews and time.monotonic() < deadline:
            message = ws.receive()
            if message.get("bytes"):
                previews.append(decode_ws_binary(message["bytes"])[0])
        assert previews[0]["node_id"] == f"edge:{edge}" and previews[0]["kind"] == kind
        assert client.post(f"{base}/tap", json={"edge_id": edge, "enabled": False}).json() == {"ok": True}
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_pad_properties_change_live(client):
    imported = client.post(
        "/api/import/gst-launch",
        json={
            "description": (
                "compositor name=mix sink_1::xpos=10 ! fakesink "
                "videotestsrc is-live=true ! mix.sink_0 videotestsrc is-live=true ! mix.sink_1"
            )
        },
    ).json()["graph"]
    project_id = client.post("/api/projects", json={"name": "pads", "graph": imported}).json()["id"]
    mixer = next(n for n in imported["nodes"] if n["factory"] == "compositor")
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        _events(ws, lambda e: e["type"] == "state" and e["state"] == "playing")
        change = {"node_id": mixer["id"], "property": "xpos", "value": 200, "pad": "sink_1"}
        result = client.post(f"{base}/property", json=change).json()
        assert result["ok"] and result["value"] == 200
        values = client.get(f"{base}/properties/{mixer['id']}").json()
        assert values["pads"]["sink_1"]["xpos"] == 200
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_verbose_debug_logs_are_throttled(client):
    project_id = _project(client, chain(("videotestsrc", {"num-buffers": 200}), "fakesink"))
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        client.post(f"/api/projects/{project_id}/runtime/start", json={"gst_debug": "*:6"})
        # The worker reports "stopped" before the API has drained its stderr backlog.
        events, _ = _events(ws, lambda e: e["type"] == "log" and "log lines dropped" in e["line"], timeout=30)
    logs = [e["line"] for e in events if e["type"] == "log"]
    assert len(logs) < 143_000


def test_restarting_replaces_the_running_pipeline(client):
    project_id = _project(client, chain(("videotestsrc", {"is-live": True}), "fakesink"))
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        _events(ws, lambda e: e["type"] == "state" and e["state"] == "playing")
        client.post(f"{base}/start", json={})
        _events(ws, lambda e: e["type"] == "state" and e["state"] == "playing")
        time.sleep(0.5)
        assert client.get(f"{base}/status").json()["state"] == "playing"
        client.post(f"{base}/stop", json={"mode": "kill"})
        _events(ws, _stopped)
    assert client.get(f"{base}/status").json()["state"] == "stopped"


def _preview_rate(ws, node_id, seconds, settle=3.0):
    """Steady preview frames per second for ``node_id`` (after the start-up latency)."""
    start, times, deadline = None, [], time.monotonic() + settle + seconds + 15
    while time.monotonic() < deadline:
        message = ws.receive()
        if not message.get("bytes"):
            continue
        if decode_ws_binary(message["bytes"])[0]["node_id"] != node_id:
            continue
        now = time.monotonic()
        start = start or now
        if now - start >= settle:
            times.append(now)
        if len(times) > 1 and times[-1] - times[0] >= seconds:
            return (len(times) - 1) / (times[-1] - times[0])
    raise AssertionError("not enough preview frames")


def test_preview_keeps_its_rate_with_high_latency_sources(client):
    imported = client.post(
        "/api/import/gst-launch",
        json={
            "description": (
                "videotestsrc is-live=true ! video/x-raw,width=640,height=360,framerate=30/1 ! videoconvert "
                "! x264enc tune=zerolatency key-int-max=30 ! rtph264pay config-interval=-1 "
                "! udpsink host=127.0.0.1 port=5004 async=false "
                'udpsrc port=5004 caps="application/x-rtp,media=video,encoding-name=H264,clock-rate=90000" '
                "! rtpjitterbuffer latency=2000 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert "
                "! autovideosink name=display"
            )
        },
    ).json()["graph"]
    project_id = client.post("/api/projects", json={"name": "latency", "graph": imported}).json()["id"]
    display = next(n for n in imported["nodes"] if n["name"] == "display")
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        assert _preview_rate(ws, display["id"], 2.0) > 12
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_preview_does_not_steer_upstream_negotiation(client):
    graph = chain(
        ("videotestsrc", {"num-buffers": 30}),
        ("capsfilter", {"caps": "video/x-raw,width=1920,height=1080"}),
        "videoconvertscale",
        "autovideosink",
    )
    project_id = _project(client, graph)
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        client.post(f"/api/projects/{project_id}/runtime/start", json={})
        events, _ = _events(ws, lambda e: e["type"] == "caps" and e["edge_id"] == "e2")
    caps = events[-1]["caps"]
    assert "width=(int)1920" in caps and "height=(int)1080" in caps


def test_preview_prefers_common_display_formats(client):
    project_id = _project(client, chain(("videotestsrc", {"num-buffers": 5}), "autovideosink"))
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        client.post(f"/api/projects/{project_id}/runtime/start", json={})
        events, _ = _events(ws, lambda e: e["type"] == "caps" and e["edge_id"] == "e0")
    assert "format=(string)I420" in events[-1]["caps"]
