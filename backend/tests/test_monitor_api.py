"""The live-pipeline monitor API, exercised against a real gst-launch process."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest


def _wait_for_dot(dot_dir: Path, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(p.suffix == ".dot" for p in dot_dir.iterdir()):
            return True
        time.sleep(0.2)
    return False


@pytest.fixture
def live_pipeline(tmp_path: Path):
    """A real GStreamer process with a dump dir, standing in for a third-party pipeline."""
    dot_dir = tmp_path / "dots"
    dot_dir.mkdir()
    env = dict(os.environ, GST_DEBUG_DUMP_DOT_DIR=str(dot_dir))
    proc = subprocess.Popen(
        ["gst-launch-1.0", "-q", "videotestsrc", "is-live=true", "!", "queue", "!", "fakesink"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_for_dot(dot_dir), "gst-launch wrote no .dot dump"
        yield proc
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)


def test_processes_lists_the_live_pipeline(client, live_pipeline):
    processes = client.get("/api/monitor/processes").json()["processes"]
    mine = next((p for p in processes if p["pid"] == live_pipeline.pid), None)
    assert mine is not None, "the live gst-launch was not discovered"
    assert "gst-launch" in mine["process"]
    assert "dot-dir" in mine["methods"]
    assert mine["dot_dir"] is not None


def test_snapshot_reconstructs_the_graph(client, live_pipeline):
    response = client.post("/api/monitor/snapshot", json={"pid": live_pipeline.pid, "method": "dot-dir"})
    assert response.status_code == 200, response.text
    pipeline = response.json()

    names = {n["name"] for n in pipeline["nodes"]}
    assert {"videotestsrc0", "queue0", "fakesink0"} <= names
    assert all(n["state"] in ("playing", "paused", "ready") for n in pipeline["nodes"])

    by_name = {n["name"]: n for n in pipeline["nodes"]}
    # Factories resolve against the real catalog of the test container.
    assert by_name["videotestsrc0"]["factory"] == "videotestsrc"
    assert by_name["videotestsrc0"]["factory_known"] is True

    # The link between the elements is reconstructed, with negotiated caps.
    pairs = {(e["source"], e["target"]) for e in pipeline["edges"]}
    ids = {n["name"]: n["id"] for n in pipeline["nodes"]}
    assert (ids["videotestsrc0"], ids["queue0"]) in pairs
    assert (ids["queue0"], ids["fakesink0"]) in pairs


def test_snapshot_unknown_pid_is_404(client):
    assert client.post("/api/monitor/snapshot", json={"pid": 2_000_000_000}).status_code == 404


def test_snapshot_via_gdb_without_a_dump_dir(client):
    """Reconstruct a pipeline that was started with no GST_DEBUG_DUMP_DOT_DIR, by attaching gdb.

    Skips when the environment does not allow ptrace (e.g. CI without CAP_SYS_PTRACE), since the
    method legitimately cannot work there.
    """
    if not shutil.which("gdb"):
        pytest.skip("gdb is not installed")
    proc = subprocess.Popen(
        ["gst-launch-1.0", "-q", "audiotestsrc", "!", "audioconvert", "!", "fakesink"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(3)
        response = client.post("/api/monitor/snapshot", json={"pid": proc.pid, "method": "gdb"})
        if response.status_code == 409 and "permission" in response.text.lower():
            pytest.skip("ptrace not permitted in this environment")
        assert response.status_code == 200, response.text
        names = {n["name"] for n in response.json()["nodes"]}
        assert {"audiotestsrc0", "audioconvert0", "fakesink0"} <= names
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
