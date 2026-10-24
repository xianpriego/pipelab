"""Every starter template must validate cleanly and run without errors."""

import json
import time

import pytest

from pipelab.storage.samples import SAMPLE_NAME, _generate
from pipelab.templates.starters import STARTERS
from tests.api_client import api_client

pytestmark = pytest.mark.runtime
RUN_SECONDS = 3.5


@pytest.fixture(scope="module")
def client(catalog, tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("templates")
    with api_client(data_dir) as client:
        media = data_dir / "media"
        deadline = time.monotonic() + 60
        while not (media / SAMPLE_NAME).exists() and time.monotonic() < deadline:
            time.sleep(0.5)
        if not (media / SAMPLE_NAME).exists():
            _generate(media)
        yield client


@pytest.mark.parametrize("starter", STARTERS, ids=lambda s: s.id)
def test_template_validates_and_runs(client, starter):
    template = next(t for t in client.get("/api/templates").json() if t["id"] == starter.id)
    if not template["available"]:
        pytest.skip(f"missing elements: {template['missing']}")
    project = client.post("/api/projects", json={"name": starter.name, "template": starter.id}).json()
    issues = client.post("/api/graph/validate", json={"graph": project["graph"]}).json()["issues"]
    assert [i["message"] for i in issues if i["severity"] == "error"] == []

    base = f"/api/projects/{project['id']}/runtime"
    errors, states, stats = [], set(), {}
    deadline = time.monotonic() + RUN_SECONDS
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        while time.monotonic() < deadline:
            message = ws.receive()
            if message.get("text") is None:
                continue
            event = json.loads(message["text"])
            if event["type"] == "bus" and event["kind"] == "error":
                errors.append(f"{event['source']}: {event['text']} ({event.get('debug')})")
            elif event["type"] == "stats":
                stats = event["edges"]
            elif event["type"] == "state":
                states.add(event["state"])
                if event["state"] in ("stopped", "error"):
                    break
        client.post(f"{base}/stop", json={"mode": "kill"})
    assert errors == []
    assert states & {"playing", "stopped"}, f"never played: {states}"
    idle = sorted(edge for edge, values in stats.items() if not values["buffers"])
    assert not idle, f"links without data: {idle}"
