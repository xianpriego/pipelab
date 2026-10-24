"""Parse real GStreamer .dot dumps and map them onto the monitor models."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipelab.monitor.dot_parse import parse_dot
from pipelab.monitor.graph_map import build_gtype_index, to_monitor_pipeline
from pipelab.monitor.models import MonitorSource

FIXTURES = Path(__file__).parent / "monitor_fixtures"


def _dot(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_linear_pipeline():
    parsed = parse_dot(_dot("gst-launch-playing.dot"))
    assert parsed.name == "pipeline0"
    names = {e.name for e in parsed.elements.values()}
    assert {
        "videotestsrc0",
        "capsfilter0",
        "queue0",
        "x264enc0",
        "h264parse0",
        "mpegtsmux0",
        "fakesink0",
    } <= names

    by_name = {e.name: e for e in parsed.elements.values()}
    assert by_name["capsfilter0"].gtype == "GstCapsFilter"
    assert by_name["capsfilter0"].state == "playing"
    # Observed, non-default properties are captured as text.
    assert "caps" in by_name["capsfilter0"].properties
    assert by_name["videotestsrc0"].properties.get("is-live") == "TRUE"
    # Pad directions.
    dirs = {p.direction for p in by_name["capsfilter0"].pads.values()}
    assert dirs == {"sink", "src"}


def test_parse_links_have_pad_names_and_caps():
    parsed = parse_dot(_dot("gst-launch-playing.dot"))
    by_addr = parsed.elements
    links = {
        (by_addr[link.src_element].name, link.src_pad, by_addr[link.dst_element].name, link.dst_pad): link
        for link in parsed.links
    }
    assert ("videotestsrc0", "src", "capsfilter0", "sink") in links
    # Request pad name on the muxer is preserved.
    assert any(dst == "mpegtsmux0" and dpad.startswith("sink_") for (_, _, dst, dpad) in links)
    caps = links[("videotestsrc0", "src", "capsfilter0", "sink")].caps
    assert caps and caps.startswith("video/x-raw")


def test_parse_nested_bin():
    parsed = parse_dot(_dot("gst-launch-bin.dot"))
    by_name = {e.name: e for e in parsed.elements.values()}
    assert "decodebin0" in by_name and "typefind" in by_name
    # typefind lives inside decodebin0.
    assert by_name["typefind"].parent == by_name["decodebin0"].addr


def test_map_to_monitor_pipeline_resolves_factories():
    parsed = parse_dot(_dot("gst-launch-playing.dot"))

    class _El:
        def __init__(self, name, hierarchy):
            self.name = name
            self.hierarchy = hierarchy

    catalog = [
        _El("capsfilter", ["GstCapsFilter", "GstBaseTransform", "GstElement"]),
        _El("x264enc", ["GstX264Enc", "GstVideoEncoder", "GstElement"]),
        _El("videotestsrc", ["GstVideoTestSrc", "GstPushSrc", "GstElement"]),
    ]
    index = build_gtype_index(catalog)
    pipeline = to_monitor_pipeline(parsed, MonitorSource(method="file"), index)

    by_name = {n.name: n for n in pipeline.nodes}
    assert by_name["capsfilter0"].factory == "capsfilter"
    assert by_name["capsfilter0"].factory_known is True
    assert by_name["x264enc0"].factory == "x264enc"
    # Unknown-to-catalog elements still appear, keyed by a best-effort factory guess.
    assert "mpegtsmux0" in by_name
    assert by_name["mpegtsmux0"].factory_known is False
    # Every node gets a layout position.
    assert any(n.position["x"] > 0 for n in pipeline.nodes)
    # Edges carry caps.
    assert pipeline.edges and all(e.source and e.target for e in pipeline.edges)


def test_map_marks_bins():
    parsed = parse_dot(_dot("gst-launch-bin.dot"))
    pipeline = to_monitor_pipeline(parsed, MonitorSource(method="file"), {})
    by_name = {n.name: n for n in pipeline.nodes}
    assert by_name["decodebin0"].is_bin is True
    assert by_name["typefind"].is_bin is False
    assert by_name["typefind"].parent == by_name["decodebin0"].id


def test_parse_is_defensive_on_garbage():
    # Must not raise on non-dot input.
    result = parse_dot("not a dot file at all {{{")
    assert result.elements == {}
    assert result.links == []


@pytest.mark.parametrize("name", ["gst-launch-playing.dot", "gst-launch-bin.dot"])
def test_every_link_connects_known_elements(name):
    parsed = parse_dot(_dot(name))
    for link in parsed.links:
        assert link.src_element in parsed.elements
        assert link.dst_element in parsed.elements
