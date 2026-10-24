"""gst-launch rendering: chains, references, quoting and parse_launch validity."""

from __future__ import annotations

import pytest

from pipelab.export.gst_launch import render, render_command, render_description
from pipelab.graph.models import Graph
from pipelab.gst import Gst
from tests.helpers import chain, graph


def linear() -> Graph:
    return chain(
        ("videotestsrc", {"num-buffers": 30, "pattern": "ball"}),
        ("capsfilter", {"caps": "video/x-raw, width=320, height=240"}),
        "videoconvert",
        "fakesink",
    )


def tee_graph() -> Graph:
    return graph(
        [
            ("src", "videotestsrc"),
            ("t", "tee"),
            ("q1", "queue"),
            ("s1", "fakesink"),
            ("q2", "queue"),
            ("s2", "fakesink"),
        ],
        [
            ("src", "src", "t", "sink"),
            ("t", "src_0", "q1", "sink"),
            ("q1", "src", "s1", "sink"),
            ("t", "src_1", "q2", "sink"),
            ("q2", "src", "s2", "sink"),
        ],
    )


def muxer_graph() -> Graph:
    return graph(
        [
            ("v", "videotestsrc"),
            ("enc", "x264enc"),
            ("parse", "h264parse"),
            ("mux", "mp4mux"),
            ("out", "filesink", {"location": "out file.mp4"}),
            ("a", "audiotestsrc"),
            ("conv", "audioconvert"),
            ("aac", "avenc_aac"),
        ],
        [
            ("v", "src", "enc", "sink"),
            ("enc", "src", "parse", "sink"),
            ("parse", "src", "mux", "video_0"),
            ("mux", "src", "out", "sink"),
            ("a", "src", "conv", "sink"),
            ("conv", "src", "aac", "sink"),
            ("aac", "src", "mux", "audio_0"),
        ],
    )


def demuxer_graph() -> Graph:
    return graph(
        [
            ("fs", "filesrc", {"location": "in.mp4"}),
            ("d", "qtdemux"),
            ("qv", "queue"),
            ("vd", "avdec_h264"),
            ("vs", "fakesink"),
            ("qa", "queue"),
            ("ad", "avdec_aac"),
            ("as", "fakesink"),
        ],
        [
            ("fs", "src", "d", "sink"),
            ("d", "video_%u", "qv", "sink"),
            ("qv", "src", "vd", "sink"),
            ("vd", "src", "vs", "sink"),
            ("d", "audio_%u", "qa", "sink"),
            ("qa", "src", "ad", "sink"),
            ("ad", "src", "as", "sink"),
        ],
    )


def decodebin_graph() -> Graph:
    return graph(
        [
            ("fs", "filesrc", {"location": "in.mp4"}),
            ("dec", "decodebin"),
            ("vc", "videoconvert"),
            ("vs", "fakesink"),
            ("ac", "audioconvert"),
            ("as", "fakesink"),
        ],
        [
            ("fs", "src", "dec", "sink"),
            ("dec", "src_%u", "vc", "sink"),
            ("vc", "src", "vs", "sink"),
            ("dec", "src_%u", "ac", "sink"),
            ("ac", "src", "as", "sink"),
        ],
    )


def compositor_graph() -> Graph:
    result = graph(
        [
            ("a", "videotestsrc"),
            ("b", "videotestsrc", {"pattern": "ball"}),
            ("c", "compositor"),
            ("k", "fakesink"),
        ],
        [("a", "src", "c", "sink_0"), ("b", "src", "c", "sink_1"), ("c", "src", "k", "sink")],
    )
    result.node("c").pad_properties = {"sink_0": {"xpos": 0}, "sink_1": {"xpos": 320, "alpha": 0.5}}
    return result


def selector_graph() -> Graph:
    return graph(
        [
            ("a", "videotestsrc"),
            ("b", "videotestsrc"),
            ("sel", "input-selector", {"active-pad": "sink_1"}),
            ("k", "fakesink"),
        ],
        [("a", "src", "sel", "sink_0"), ("b", "src", "sel", "sink_1"), ("sel", "src", "k", "sink")],
    )


def test_linear_chain_inlines_caps(catalog):
    assert render_description(linear(), catalog) == (
        "videotestsrc num-buffers=30 pattern=ball ! video/x-raw,width=320,height=240 ! "
        "videoconvert ! fakesink"
    )


def test_command_is_shell_ready(catalog):
    command = render_command(linear(), catalog)
    assert command.startswith("gst-launch-1.0 -e \\\n  videotestsrc")
    assert '! "video/x-raw,width=320,height=240" !' in command


def test_tee_branches_use_references(catalog):
    assert render_description(tee_graph(), catalog) == (
        "videotestsrc ! tee name=t ! queue ! fakesink t. ! queue ! fakesink"
    )
    lines = render_command(tee_graph(), catalog).splitlines()
    assert lines[1].strip().endswith("\\") and lines[2].strip().startswith("t. ! queue")


def test_muxer_request_pads_are_explicit(catalog):
    description = render_description(muxer_graph(), catalog)
    assert "h264parse ! mux.video_0" in description
    assert "avenc_aac ! mux.audio_0" in description
    assert 'mp4mux name=mux ! filesink location="out file.mp4"' in description


def test_demuxer_branches_use_concrete_sometimes_pads(catalog):
    description = render_description(demuxer_graph(), catalog)
    assert "qtdemux name=d" in description
    assert "d.video_0 ! queue ! avdec_h264 ! fakesink" in description
    assert "d.audio_0 ! queue ! avdec_aac ! fakesink" in description


def test_single_sometimes_template_links_implicitly(catalog):
    description = render_description(decodebin_graph(), catalog)
    assert description.startswith("filesrc location=in.mp4 ! decodebin name=dec ! videoconvert ! fakesink")
    assert "dec. ! audioconvert ! fakesink" in description


def test_pad_properties_and_explicit_sink_pads(catalog):
    description = render_description(compositor_graph(), catalog)
    assert "compositor name=c sink_0::xpos=0 sink_1::alpha=0.5 sink_1::xpos=320 ! fakesink" in description
    assert "videotestsrc ! c.sink_0" in description
    assert "videotestsrc pattern=ball ! c.sink_1" in description


def test_pad_typed_properties_are_reported_not_rendered(catalog):
    assert "active-pad" not in render_description(selector_graph(), catalog)
    script = render(selector_graph(), catalog, "selector")
    assert script.startswith("#!/bin/sh\n")
    assert "#   sel.active-pad=sink_1" in script


def test_values_are_quoted_for_each_syntax(catalog):
    special = chain("videotestsrc", ("filesink", {"location": 'a "b" $HOME.mp4'}))
    assert render_description(special, catalog).endswith('location="a \\"b\\" $HOME.mp4"')
    assert render_command(special, catalog).endswith('location="a \\"b\\" \\$HOME.mp4"')


def test_unreferenced_elements_are_not_named(catalog):
    assert "name=" not in render_description(linear(), catalog)


def test_empty_graph(catalog):
    assert render_description(Graph(), catalog) == ""
    assert render_command(Graph(), catalog) == "gst-launch-1.0 -e"


@pytest.mark.parametrize(
    "factory",
    [linear, tee_graph, muxer_graph, demuxer_graph, decodebin_graph, compositor_graph, selector_graph],
)
def test_gst_parse_launch_accepts_export(catalog, factory):
    built = factory()
    pipeline = Gst.parse_launch(render_description(built, catalog))
    assert pipeline.get_children_count() == len(built.nodes)
    pipeline.set_state(Gst.State.NULL)
