"""Starter components (install into the library) and component files (export / import)."""

import pytest

from pipelab.components.models import Component
from pipelab.components.overlay import overlay_catalog
from pipelab.components.starters import STARTER_COMPONENTS, StarterComponents
from pipelab.components.validate import validate_component
from pipelab.graph.analyzer import Analyzer
from tests.helpers import graph as graph_of
from tests.runtime_helpers import create_project, events_until, is_stopped


@pytest.mark.parametrize("starter_id", [s.id for s in STARTER_COMPONENTS])
def test_available_starters_are_valid_components(catalog, starter_id):
    starters = StarterComponents(catalog)
    if starter_id in {info.id for info in starters.list() if not info.available}:
        pytest.skip("elements not installed on this machine (NVIDIA without a GPU)")
    component = starters.definition(starter_id)
    analyzer = Analyzer(overlay_catalog(catalog, {starter_id: component}), {starter_id: component})
    assert [i.message for i in validate_component(analyzer, component) if i.severity == "error"] == []
    virtual = analyzer.catalog.get(component.factory)
    assert {pad.name for pad in virtual.pad_templates} == {port.name for port in component.ports}


def test_install_starters_and_share_them_as_files(client):
    listing = {s["id"]: s for s in client.get("/api/components/starters").json()}
    assert listing["h264-encoder"]["available"] and "rtsp-h264-input" in listing
    assert client.post("/api/components/starters/video-scaler").status_code == 201
    assert client.post("/api/components/starters/video-scaler").status_code == 409
    assert client.post("/api/components/starters/nope").status_code == 404

    # A component containing the scaler: its file carries both, nested first.
    outer = Component(
        id="scaled-test",
        name="Scaled test source",
        graph=graph_of([("s", "videotestsrc"), ("v", "component:video-scaler")], [("s", "src", "v", "sink")]),
        ports=[{"name": "src", "direction": "src", "node_id": "v", "pad": "src"}],
    )
    client.put("/api/components/scaled-test", json=outer.model_dump(mode="json"))
    bundle = client.get("/api/components/scaled-test/bundle").json()
    assert bundle["format"] == "pipelab-components"
    assert [c["id"] for c in bundle["components"]] == ["video-scaler", "scaled-test"]

    conflict = client.post("/api/components/import", json={"bundle": bundle})
    assert conflict.status_code == 409 and "video-scaler" in conflict.json()["detail"]
    imported = client.post("/api/components/import", json={"bundle": bundle, "overwrite": True}).json()
    assert imported == {"imported": ["video-scaler", "scaled-test"]}
    assert client.get("/api/components/scaled-test").json()["version"] == 2
    renamed = {**bundle, "components": [{**bundle["components"][0], "id": "Bad id"}]}
    assert client.post("/api/components/import", json={"bundle": renamed}).status_code == 422


@pytest.mark.runtime
def test_encoder_and_recorder_starters_run(client, data_dir):
    for starter in ("video-scaler", "h264-encoder", "mp4-recorder"):
        client.post(f"/api/components/starters/{starter}")
    graph = graph_of(
        [
            ("src", "videotestsrc", {"num-buffers": 60}),
            ("tee", "tee"),
            ("q", "queue"),
            ("scale", "component:video-scaler", {"caps": "video/x-raw,width=320,height=240"}),
            ("enc", "component:h264-encoder", {"bitrate": 500}),
            ("out", "fakesink"),
            ("rec", "component:mp4-recorder", {"location": "starter-%02d.mp4", "segment-duration": 0}),
        ],
        [
            ("src", "src", "tee", "sink"),
            ("tee", "src_%u", "q", "sink"),
            ("q", "src", "scale", "sink"),
            ("scale", "src", "enc", "sink"),
            ("enc", "src", "out", "sink"),
            ("tee", "src_%u", "rec", "sink"),
        ],
    )
    project_id = create_project(client, graph)
    with client.websocket_connect(f"/api/projects/{project_id}/runtime/ws") as ws:
        client.post(f"/api/projects/{project_id}/runtime/start", json={})
        events, _ = events_until(ws, is_stopped, timeout=30)
    assert [e["text"] for e in events if e["type"] == "bus" and e["kind"] == "error"] == []
    assert any(e["type"] == "bus" and e["kind"] == "eos" for e in events)
    recording = data_dir / "media" / "starter-00.mp4"
    assert recording.exists() and recording.stat().st_size > 1000
