"""gst-launch importer: values, names, pad resolution and round trips."""

from __future__ import annotations

from collections import Counter

import pytest

from pipelab.export.gst_launch import render_description
from pipelab.graph.editing import default_name
from pipelab.graph.models import Graph
from pipelab.gst import Gst
from pipelab.importer import import_gst_launch
from tests.helpers import named_links


def test_values_are_typed_from_the_catalog(catalog):
    result = import_gst_launch(
        "gst-launch-1.0 -e videotestsrc is-live=true num-buffers=30 pattern=ball ! "
        "volume volume=0.5 ! fakesink",
        catalog,
    )
    source, volume, _ = result.graph.nodes
    assert source.properties == {"is-live": True, "num-buffers": 30, "pattern": "ball"}
    assert volume.properties == {"volume": 0.5}
    assert result.warnings == []


def test_names_are_kept_or_generated(catalog):
    graph = import_gst_launch("videotestsrc name=src ! queue ! queue ! avdec_h264 ! fakesink", catalog).graph
    assert [n.name for n in graph.nodes] == ["src", "queue0", "queue1", "avdec_h264-0", "fakesink0"]
    assert all("name" not in n.properties for n in graph.nodes)
    assert default_name("queue", {"queue0"}) == "queue1"


def test_caps_become_capsfilters(catalog):
    graph = import_gst_launch(
        'videotestsrc ! "video/x-raw(memory:CUDAMemory), format=NV12" ! fakesink', catalog
    ).graph
    assert graph.nodes[1].factory == "capsfilter"
    assert graph.nodes[1].properties == {"caps": "video/x-raw(memory:CUDAMemory), format=NV12"}
    assert named_links(graph)[0] == ("videotestsrc0", "src", "capsfilter0", "sink")


def test_muxer_pads_follow_caps_and_forward_references(catalog):
    graph = import_gst_launch(
        "audiotestsrc ! avenc_aac ! mux. videotestsrc ! x264enc ! mux. mp4mux name=mux ! fakesink", catalog
    ).graph
    assert ("avenc_aac0", "src", "mux", "audio_0") in named_links(graph)
    assert ("x264enc0", "src", "mux", "video_0") in named_links(graph)


def test_explicit_request_template_gets_a_concrete_pad(catalog):
    graph = import_gst_launch("videotestsrc ! x264enc ! m.video_%u mp4mux name=m ! fakesink", catalog).graph
    assert ("x264enc0", "src", "m", "video_0") in named_links(graph)


def test_tee_requests_consecutive_pads(catalog):
    graph = import_gst_launch(
        "videotestsrc ! tee name=t ! fakesink t. ! fakesink t. ! fakesink", catalog
    ).graph
    assert [link[1] for link in named_links(graph) if link[0] == "t"] == ["src_0", "src_1", "src_2"]


def test_demuxer_pads_follow_the_downstream_media(catalog):
    graph = import_gst_launch(
        "filesrc location=a.mp4 ! qtdemux name=d "
        "d. ! queue ! aacparse ! fakesink d. ! queue ! h264parse ! fakesink",
        catalog,
    ).graph
    assert ("d", "audio_%u", "queue0", "sink") in named_links(graph)
    assert ("d", "video_%u", "queue1", "sink") in named_links(graph)


def test_concrete_sometimes_pad_maps_to_its_template(catalog):
    graph = import_gst_launch("filesrc ! qtdemux name=d d.video_0 ! fakesink", catalog).graph
    assert ("d", "video_%u", "fakesink0", "sink") in named_links(graph)


def test_pad_properties_are_typed(catalog):
    graph = import_gst_launch(
        "compositor name=c sink_1::xpos=320 sink_1::alpha=0.5 ! fakesink "
        "videotestsrc ! c.sink_0 videotestsrc ! c.sink_1",
        catalog,
    ).graph
    assert graph.node_by_name("c").pad_properties == {"sink_1": {"xpos": 320, "alpha": 0.5}}
    assert ("videotestsrc1", "src", "c", "sink_1") in named_links(graph)


def test_problems_become_warnings(catalog):
    result = import_gst_launch("nosuchelement ! fakesink videotestsrc bogus=1 ! nobody.sink", catalog)
    assert [n.factory for n in result.graph.nodes] == ["nosuchelement", "fakesink", "videotestsrc"]
    assert any("not installed" in w for w in result.warnings)
    assert any("no property 'bogus'" in w for w in result.warnings)
    assert any("'nobody.'" in w for w in result.warnings)


def test_graph_is_laid_out_left_to_right(catalog):
    graph = import_gst_launch("videotestsrc ! videoconvert ! fakesink", catalog).graph
    xs = [n.position.x for n in graph.nodes]
    assert xs == sorted(xs) and len(set(xs)) == 3


def test_empty_description_warns(catalog):
    assert import_gst_launch("gst-launch-1.0 -e", catalog).warnings


def _signature(graph: Graph, node_id: str) -> tuple:
    node = graph.node(node_id)
    properties = dict(node.properties)
    if node.factory == "capsfilter" and "caps" in properties:
        properties["caps"] = Gst.Caps.from_string(str(properties["caps"])).to_string()
    pads = tuple(sorted((pad, tuple(sorted(v.items()))) for pad, v in node.pad_properties.items()))
    return node.factory, tuple(sorted(properties.items())), pads


def canonical(graph: Graph) -> tuple[Counter, Counter]:
    nodes = Counter(_signature(graph, n.id) for n in graph.nodes)
    edges = Counter(
        (_signature(graph, e.source), e.source_pad, _signature(graph, e.target), e.target_pad)
        for e in graph.edges
    )
    return nodes, edges


ROUND_TRIPS = [
    "videotestsrc is-live=true pattern=ball ! video/x-raw, width=640, height=480 ! "
    "videoconvert ! fakesink sync=false",
    "videotestsrc ! tee name=t ! queue ! fakesink t. ! queue leaky=downstream ! fakesink",
    "videotestsrc ! x264enc tune=zerolatency ! h264parse ! mux. audiotestsrc ! avenc_aac ! mux. "
    'mp4mux name=mux ! filesink location="out file.mp4"',
    "filesrc location=a.mp4 ! qtdemux name=d d.video_0 ! queue ! h264parse ! avdec_h264 ! fakesink "
    "d.audio_0 ! queue ! aacparse ! avdec_aac ! fakesink",
    "compositor name=c sink_0::xpos=0 sink_1::xpos=320 ! videoconvert ! fakesink "
    "videotestsrc ! c.sink_0 videotestsrc pattern=ball ! c.sink_1",
    "uridecodebin uri=file:///a.mp4 ! videoconvert ! fakesink",
]


@pytest.mark.parametrize("description", ROUND_TRIPS)
def test_import_export_import_round_trip(catalog, description):
    first = import_gst_launch(description, catalog)
    assert first.warnings == []
    exported = render_description(first.graph, catalog)
    second = import_gst_launch(exported, catalog)
    assert second.warnings == []
    assert canonical(second.graph) == canonical(first.graph)
    Gst.parse_launch(exported).set_state(Gst.State.NULL)
