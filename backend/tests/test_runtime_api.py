"""Runtime API behaviour that does not depend on what the pipeline does."""

import time

import pytest
from starlette.websockets import WebSocketDisconnect

from pipelab.gst import Gst
from pipelab.runtime.worker.encoder import PreviewSettings
from pipelab.runtime.worker.taps import LinkTap
from tests.component_fixtures import source_component
from tests.helpers import chain
from tests.runtime_helpers import create_project, events_until, is_playing

pytestmark = pytest.mark.runtime


def test_live_changes_are_checked_against_the_running_graph(client):
    # The project is saved empty: the run uses the editor's unsaved graph.
    project_id = create_project(client, chain("fakesink"))
    base = f"/api/projects/{project_id}/runtime"
    running = chain(("videotestsrc", {"is-live": True}), "fakesink")
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={"graph": running.model_dump()})
        events_until(ws, is_playing)
        rejected = client.post(
            f"{base}/property", json={"node_id": "n0", "property": "pattern", "value": "nope"}
        )
        assert rejected.status_code == 422 and "pattern" in rejected.text
        accepted = client.post(
            f"{base}/property", json={"node_id": "n0", "property": "pattern", "value": "ball"}
        )
        assert accepted.status_code == 200 and accepted.json()["ok"] is True
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_inner_elements_of_instances_are_checked_too(client):
    client.put("/api/components/test-source", json=source_component().model_dump(mode="json"))
    project_id = create_project(client, chain("component:test-source", "fakesink"))
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        events_until(ws, is_playing)
        rejected = client.post(
            f"{base}/property", json={"node_id": "n0/s", "property": "pattern", "value": "nope"}
        )
        assert rejected.status_code == 422
        current = client.get(f"{base}/properties/n0/s")
        assert current.status_code == 200 and "pattern" in current.json()["properties"]
        client.post(f"{base}/stop", json={"mode": "kill"})


def test_unknown_projects_have_no_event_stream(client):
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        client.websocket_connect("/api/projects/nope/runtime/ws"),
    ):
        pass
    assert refused.value.code == 4404


def test_deleting_a_project_discards_its_runtime(client):
    project_id = create_project(client, chain("fakesink"))
    client.get(f"/api/projects/{project_id}/runtime/status")
    runtime = client.app.state.services.runtime
    assert project_id in runtime._sessions
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert project_id not in runtime._sessions


def test_taps_copy_buffer_lists():
    """Payloaders push buffer lists: the tap must see their buffers."""
    caps = "audio/x-raw,format=F32LE,rate=48000,channels=2,layout=interleaved"
    pipeline = Gst.parse_launch(f"appsrc name=src format=time caps={caps} ! fakesink sync=false")
    source = pipeline.get_by_name("src")
    pipeline.set_state(Gst.State.PLAYING)
    frames = []

    def buffers(count: int) -> Gst.BufferList:
        listing = Gst.BufferList.new()
        for _ in range(count):
            listing.insert(-1, Gst.Buffer.new_wrapped(bytes(4 * 2 * 480)))
        return listing

    source.emit("push-buffer-list", buffers(1))  # negotiates the caps the tap needs
    deadline = time.monotonic() + 5
    pad = source.get_static_pad("src")
    while pad.get_current_caps() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    tap = LinkTap("e0", pad, PreviewSettings(), lambda header, payload=b"": frames.append(header))
    for _ in range(20):
        source.emit("push-buffer-list", buffers(10))
    while not frames and time.monotonic() < deadline:
        time.sleep(0.05)
    tap.close()
    pipeline.set_state(Gst.State.NULL)
    assert frames and frames[0]["node_id"] == "edge:e0" and frames[0]["kind"] == "audio"
