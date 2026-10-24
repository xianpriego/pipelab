"""Runtime inspection: selector state, link probes and negotiation diagnosis."""

import pytest

from tests.helpers import chain
from tests.runtime_helpers import create_project, events_until, import_project, is_playing

pytestmark = pytest.mark.runtime

SELECTOR = (
    "input-selector name=sel ! fakesink videotestsrc is-live=true ! sel.sink_0 "
    "videotestsrc is-live=true pattern=ball ! sel.sink_1"
)


def _selector_events(events, node_id):
    return [e for e in events if e["type"] == "property" and e["node_id"] == node_id]


def test_selector_reports_its_active_pad(client):
    project_id, graph = import_project(client, SELECTOR)
    selector = next(n for n in graph["nodes"] if n["factory"] == "input-selector")
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events, _ = events_until(ws, lambda e: e["type"] == "property" and e["origin"] == "runtime")
        assert events[-1]["node_id"] == selector["id"] and events[-1]["value"] == "sink_0"
        client.post(
            f"{base}/property", json={"node_id": selector["id"], "property": "active-pad", "value": "sink_1"}
        )
        events_until(
            ws, lambda e: e["type"] == "property" and e.get("origin") == "runtime" and e["value"] == "sink_1"
        )
    with client.websocket_connect(f"{base}/ws") as ws:  # a new client gets the current value replayed
        events, _ = events_until(ws, lambda e: e["type"] == "property")
        assert _selector_events(events, selector["id"])[-1]["value"] == "sink_1"
    client.post(f"{base}/stop", json={"mode": "kill"})


def test_probe_records_buffers_crossing_a_link(client):
    project_id = create_project(client, chain(("videotestsrc", {"is-live": True}), "x264enc", "fakesink"))
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events_until(ws, is_playing)
        assert client.post(f"{base}/probe", json={"edge_id": "e1"}).json() == {"ok": True}
        events, _ = events_until(ws, lambda e: e["type"] == "probe" and len(e["items"]) >= 3)
        buffers = [i for i in events[-1]["items"] if i["kind"] == "buffer"]
        assert buffers and all(b["size"] > 0 and b["pts"] is not None for b in buffers)
        assert any("delta-unit" not in b["flags"] for b in buffers) or any(b["flags"] for b in buffers)
        assert client.post(f"{base}/probe", json={"edge_id": "e1", "enabled": False}).json() == {"ok": True}
        assert client.post(f"{base}/probe", json={"edge_id": "nope"}).json()["ok"] is False
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_not_negotiated_errors_name_the_link_and_field(client):
    # Like an RTSP camera: the depayloader learns the size from the stream and
    # pushes caps that the element downstream cannot accept.
    project_id, graph = import_project(
        client,
        "videotestsrc is-live=true ! video/x-raw,width=1280,height=720 ! x264enc tune=zerolatency "
        "! rtph264pay config-interval=-1 ! udpsink host=127.0.0.1 port=5006 async=false "
        'udpsrc port=5006 caps="application/x-rtp,media=video,encoding-name=H264,clock-rate=90000" '
        '! rtph264depay ! h264parse name=parse ! capsfilter name=limit caps="video/x-h264,width=[1,1000]" '
        "! fakesink",
    )
    names = {n["id"]: n["name"] for n in graph["nodes"]}
    edge = next(e for e in graph["edges"] if names[e["source"]] == "parse")
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        client.post(f"/api/projects/{project_id}/runtime/start", json={})
        events, _ = events_until(ws, lambda e: e["type"] == "bus" and e["kind"] == "error")
    error = events[-1]
    assert error["edge_id"] == edge["id"]
    assert "parse.src → limit.sink" in error["hint"] and "width=1280 not in [ 1, 1000 ]" in error["hint"]
    client.post(f"/api/projects/{project_id}/runtime/stop", json={"mode": "kill"})


def test_refused_dynamic_links_explain_the_caps(client):
    project_id, _graph = import_project(
        client,
        "videotestsrc num-buffers=30 ! video/x-raw,width=1280,height=720 ! x264enc ! h264parse "
        "! matroskamux ! matroskademux name=demux demux. ! h264parse "
        '! capsfilter caps="video/x-h264,width=[1,1000]" ! fakesink',
    )
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        client.post(f"/api/projects/{project_id}/runtime/start", json={})
        events, _ = events_until(ws, lambda e: e["type"] == "bus" and "cannot be linked" in e.get("text", ""))
    assert "width=1280 not in [ 1, 1000 ]" in events[-1]["text"]
    client.post(f"/api/projects/{project_id}/runtime/stop", json={"mode": "kill"})
