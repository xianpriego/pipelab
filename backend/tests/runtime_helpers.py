"""Helpers for tests that drive real pipelines through the API."""

from __future__ import annotations

import json
import struct
import time


def create_project(client, graph, name: str = "rt") -> str:
    return client.post("/api/projects", json={"name": name, "graph": graph.model_dump()}).json()["id"]


def import_project(client, description: str, name: str = "rt") -> tuple[str, dict]:
    graph = client.post("/api/import/gst-launch", json={"description": description}).json()["graph"]
    return client.post("/api/projects", json={"name": name, "graph": graph}).json()["id"], graph


def events_until(ws, until, timeout: float = 15.0):
    """Collect JSON events (and decode binary preview headers) until ``until(event)``."""
    events, previews, deadline = [], [], time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = ws.receive()
        if message.get("bytes"):
            size = struct.unpack(">I", message["bytes"][:4])[0]
            previews.append(json.loads(message["bytes"][4 : 4 + size]))
            continue
        event = json.loads(message["text"])
        events.append(event)
        if until(event):
            return events, previews
    raise AssertionError(f"condition not met, last events: {events[-5:]}")


def is_stopped(event) -> bool:
    return event["type"] == "state" and event["state"] in ("stopped", "error")


def is_playing(event) -> bool:
    return event["type"] == "state" and event["state"] == "playing"
