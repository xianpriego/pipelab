from tests.helpers import chain


def test_health_and_catalog(client):
    health = client.get("/api/health").json()
    assert health["catalog"]["state"] == "ready"
    elements = client.get("/api/catalog").json()["elements"]
    assert len(elements) > 1000
    by_name = {e["name"]: e for e in elements}
    assert by_name["autovideosink"]["preview"] == "video"
    assert by_name["pulsesink"]["preview"] == "audio"
    assert by_name["fakevideosink"]["preview"] is None
    assert by_name["input-selector"]["selectors"] == ["active-pad"]
    assert by_name["output-selector"]["selectors"] == ["active-pad"]
    assert by_name["queue"]["selectors"] == []
    info = client.get("/api/catalog/videotestsrc").json()
    assert any(p["name"] == "pattern" for p in info["properties"])
    assert client.get("/api/catalog/nope").status_code == 404


def test_project_lifecycle(client):
    created = client.post("/api/projects", json={"name": "Demo", "template": "video-test"})
    assert created.status_code == 201
    project = created.json()
    assert len(project["graph"]["nodes"]) >= 4
    project_id = project["id"]
    renamed = client.put(f"/api/projects/{project_id}", json={"name": "Renamed"}).json()
    assert renamed["name"] == "Renamed" and renamed["graph"] == project["graph"]
    copy = client.post(f"/api/projects/{project_id}/duplicate").json()
    assert copy["name"] == "Renamed (copy)"
    ids = {p["id"] for p in client.get("/api/projects").json()}
    assert {project_id, copy["id"]} <= ids
    assert client.delete(f"/api/projects/{copy['id']}").status_code == 204
    assert client.get(f"/api/projects/{copy['id']}").status_code == 404


def test_templates_are_available(client):
    templates = {t["id"]: t for t in client.get("/api/templates").json()}
    assert templates["video-test"]["available"]
    assert templates["record-mp4"]["available"]


def test_graph_endpoints(client):
    graph = chain("videotestsrc", "x264enc").model_dump()
    edge = {"id": "new", "source": "n1", "source_pad": "src", "target": "n0", "target_pad": "sink"}
    result = client.post("/api/graph/check-link", json={"graph": graph, "edge": edge}).json()
    assert result["allowed"] is False
    issues = client.post("/api/graph/validate", json={"graph": graph}).json()["issues"]
    assert any(i["rule"] == "no-sink" for i in issues)
    fix = {"kind": "set_property", "node_id": "n1", "property": "tune", "value": "zerolatency"}
    fixed = client.post("/api/graph/apply-fix", json={"graph": graph, "fix": fix}).json()["graph"]
    assert fixed["nodes"][1]["properties"]["tune"] == "zerolatency"
    laid_out = client.post("/api/graph/layout", json={"graph": graph}).json()["graph"]
    assert laid_out["nodes"][1]["position"]["x"] > laid_out["nodes"][0]["position"]["x"]


def test_export_and_import(client):
    formats = {f["id"] for f in client.get("/api/export/formats").json()}
    assert {"gst-launch", "python", "c", "rust", "json"} <= formats
    graph = chain("videotestsrc", "fakesink").model_dump()
    exported = client.post("/api/export", json={"graph": graph, "format": "gst-launch"}).json()
    assert "videotestsrc ! fakesink" in exported["content"]
    imported = client.post("/api/import/gst-launch", json={"description": "videotestsrc ! fakesink"}).json()
    assert [n["factory"] for n in imported["graph"]["nodes"]] == ["videotestsrc", "fakesink"]
    assert client.post("/api/export", json={"graph": graph, "format": "nope"}).status_code == 404


def test_media(client):
    uploaded = client.post("/api/media", files={"file": ("clip.txt", b"hello")}).json()
    assert uploaded["path"] == "clip.txt"
    assert any(f["path"] == "clip.txt" for f in client.get("/api/media").json()["files"])
    assert client.get("/api/media/clip.txt").content == b"hello"
    assert client.get("/api/media/../../etc/passwd").status_code == 404
    assert client.delete("/api/media/clip.txt").status_code == 204
