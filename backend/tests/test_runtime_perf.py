"""Performance data of a running pipeline: element latency, queue levels and streaming threads."""

import pytest

from tests.runtime_helpers import events_until, import_project

pytestmark = pytest.mark.runtime


def _node(graph, name):
    return next(node["id"] for node in graph["nodes"] if node["name"] == name)


def test_slow_element_fills_the_queue_before_it(client):
    # 30 fps live source; "slow" takes 50 ms per buffer, so the small queue in front of it fills up.
    project_id, graph = import_project(
        client,
        "videotestsrc is-live=true ! video/x-raw,width=160,height=120,framerate=30/1 "
        "! videoconvert name=conv "
        "! queue name=q max-size-buffers=5 max-size-time=0 max-size-bytes=0 "
        "! identity name=slow sleep-time=50000 ! fakesink",
    )
    base = f"/api/projects/{project_id}/runtime"
    with client.websocket_connect(f"{base}/ws") as ws:
        client.post(f"{base}/start", json={})
        for _ in range(4):
            events_until(ws, lambda e: e["type"] == "stats")
        events, _ = events_until(ws, lambda e: e["type"] == "stats")
        stats = events[-1]
        client.post(f"{base}/stop", json={"mode": "kill"})

    slow, queue, conv = _node(graph, "slow"), _node(graph, "q"), _node(graph, "conv")
    assert 45 <= stats["elements"][slow]["avg_ms"] < 150, stats["elements"]
    assert stats["elements"][conv]["avg_ms"] < 45
    level = stats["queues"][queue]
    assert level["max_buffers"] == 5 and level["fill"] >= 0.8 and level["overruns"] > 0, level
    # Two streaming threads: the source's (up to the queue) and the queue's (after it).
    threads = stats["threads"]
    assert len(threads) == 2 and all(t["cpu"] is not None for t in threads), threads
    assert [t["name"] for t in threads if any(e in t["edges"] for e in _out_edges(graph, queue))] == ["q:src"]


def _out_edges(graph, node_id):
    return [edge["id"] for edge in graph["edges"] if edge["source"] == node_id]
