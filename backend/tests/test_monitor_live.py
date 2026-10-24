"""Tracer-log parsing and the live-statistics monitor API."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from pipelab.monitor.tracer_parse import StatsAccumulator, parse_record

FIXTURES = Path(__file__).parent / "monitor_fixtures"


def test_parse_record_reads_fields():
    kind, fields = parse_record(
        "0:00:01 12 12 TRACE GST_TRACER x.c:1:f: buffer, pad-ix=(uint)4, element-ix=(uint)2, "
        "peer-element-ix=(uint)3, peer-pad-ix=(uint)5, buffer-size=(uint)1000, "
        "have-buffer-pts=(boolean)1, buffer-pts=(guint64)500;"
    )
    assert kind == "buffer"
    assert fields["pad-ix"] == "4"
    assert fields["buffer-size"] == "1000"


def test_parse_record_ignores_non_records():
    assert parse_record("just a log line") is None


def test_accumulator_aggregates_real_log():
    accum = StatsAccumulator()
    for line in (FIXTURES / "tracer-records.log").read_text().splitlines():
        accum.ingest_line(line)

    # The index→name maps are learned from new-element/new-pad records.
    assert set(accum.elements.values()) >= {
        "videotestsrc0",
        "videoconvert0",
        "queue0",
        "x264enc0",
        "fakesink0",
    }

    stats = accum.drain(2.0)  # the fixture spans about two seconds

    raw_link = stats["edges"].get("videotestsrc0:src>videoconvert0:sink")
    assert raw_link is not None
    assert raw_link["buffers"] == 60
    assert 25 <= raw_link["fps"] <= 35  # ~30 fps
    assert raw_link["bitrate"] > 0

    # Per-element latency for the encoder is present and large; the raw filters are small.
    assert stats["elements"]["x264enc0"]["avg_ms"] > stats["elements"]["videoconvert0"]["avg_ms"]
    # Streaming threads each carry the links they push.
    assert stats["threads"] and all("edges" in t for t in stats["threads"])
    # End-to-end latency from the latency tracer.
    assert stats["end_to_end"] and stats["end_to_end"]["samples"] > 0


def test_accumulator_resets_between_windows():
    accum = StatsAccumulator()
    for line in (FIXTURES / "tracer-records.log").read_text().splitlines():
        accum.ingest_line(line)
    accum.drain(1.0)
    second = accum.drain(1.0)
    assert second["edges"] == {} and second["elements"] == {}
    # But the name maps survive, so new buffers can still be mapped.
    assert accum.elements


@pytest.fixture
def traced_pipeline(tmp_path: Path):
    """A real pipeline launched with the GStreamer tracers, like a production process would be."""
    log = tmp_path / "tracer.log"
    env = dict(
        os.environ,
        GST_TRACERS="stats;latency",
        GST_DEBUG="GST_TRACER:7",
        GST_DEBUG_FILE=str(log),
        GST_DEBUG_NO_COLOR="1",
        GST_DEBUG_DUMP_DOT_DIR=str(tmp_path),
    )
    proc = subprocess.Popen(
        [
            "gst-launch-1.0",
            "-q",
            "videotestsrc",
            "is-live=true",
            "!",
            "videoconvert",
            "!",
            "fakesink",
            "sync=true",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 10
        while time.time() < deadline and not (
            log.exists() and any(p.suffix == ".dot" for p in tmp_path.iterdir())
        ):
            time.sleep(0.2)
        yield proc
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)


def test_process_reports_full_stats_capability(client, traced_pipeline):
    processes = client.get("/api/monitor/processes").json()["processes"]
    mine = next((p for p in processes if p["pid"] == traced_pipeline.pid), None)
    assert mine is not None
    assert mine["full_stats"] is True
    assert "stats" in mine["tracers"]
    assert mine["tracer_log"] is not None


def test_live_stats_flow(client, traced_pipeline):
    # Structure first, so the live tailer can map names to ids.
    snapshot = client.post("/api/monitor/snapshot", json={"pid": traced_pipeline.pid, "method": "dot-dir"})
    assert snapshot.status_code == 200, snapshot.text

    # First poll primes the tailer; let buffers accumulate, then measure.
    client.get(f"/api/monitor/live?pid={traced_pipeline.pid}")
    time.sleep(1.5)
    stats = client.get(f"/api/monitor/live?pid={traced_pipeline.pid}").json()

    assert stats["available"] is True
    assert stats["edges"], "no per-link stats were produced"
    # Every stats key is an edge id of the snapshot.
    edge_ids = {e["id"] for e in snapshot.json()["edges"]}
    assert set(stats["edges"]) <= edge_ids
    assert any(v["fps"] > 0 for v in stats["edges"].values())


def test_live_stats_unavailable_without_tracers(client):
    """A process without the tracers reports live stats as unavailable, with guidance."""
    proc = subprocess.Popen(
        ["gst-launch-1.0", "-q", "audiotestsrc", "!", "fakesink"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(2)
        result = client.get(f"/api/monitor/live?pid={proc.pid}").json()
        assert result["available"] is False
        assert "GST_TRACERS" in result["reason"]
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
