from pipelab.graph.link_check import check_link
from pipelab.graph.models import Edge
from tests.helpers import graph


def _check(analyzer, nodes, edges, new):
    g = graph(nodes, edges)
    return check_link(
        analyzer, g, Edge(id="new", source=new[0], source_pad=new[1], target=new[2], target_pad=new[3])
    )


def _rules(result):
    return {issue.rule for issue in result.issues}


def test_compatible_raw_link_suggests_converter_for_safety(analyzer):
    result = _check(analyzer, [("a", "videotestsrc"), ("b", "x264enc")], [], ("a", "src", "b", "sink"))
    assert result.allowed
    assert "safety-converter" in _rules(result)
    assert result.issues[0].suggestions[0].fix.elements[0].factory == "videoconvert"


def test_incompatible_link_is_rejected_with_encoder_bridge(analyzer):
    result = _check(analyzer, [("a", "videotestsrc"), ("b", "rtph264pay")], [], ("a", "src", "b", "sink"))
    assert not result.allowed
    titles = [s.title for s in result.issues[0].suggestions]
    assert titles[0] == "Insert x264enc"


def test_request_pad_template_is_resolved_to_next_free_pad(analyzer):
    result = _check(
        analyzer,
        [("enc", "x264enc"), ("enc2", "x264enc"), ("mux", "mp4mux")],
        [("enc", "src", "mux", "video_0")],
        ("enc2", "src", "mux", "video_%u"),
    )
    assert result.edge.target_pad == "video_1"


def test_caps_flow_through_queue_catches_wrong_media(analyzer):
    result = _check(
        analyzer,
        [("enc", "x264enc"), ("q", "queue"), ("sink", "autoaudiosink")],
        [("enc", "src", "q", "sink")],
        ("q", "src", "sink", "sink"),
    )
    assert not result.allowed
    assert "caps-incompatible" in _rules(result)


def test_capsfilter_memory_feature_requires_download(analyzer):
    result = (
        _check(
            analyzer,
            [
                ("dec", "nvh264dec"),
                ("f", "capsfilter", {"caps": "video/x-raw(memory:CUDAMemory)"}),
                ("enc", "x264enc"),
            ],
            [("dec", "src", "f", "sink")],
            ("f", "src", "enc", "sink"),
        )
        if "nvh264dec" in analyzer.catalog
        else None
    )
    if result is None:
        return
    assert not result.allowed
    assert result.issues[0].suggestions[0].title == "Insert cudadownload"


def test_depayloader_to_decoder_asks_for_parser(analyzer):
    result = _check(analyzer, [("d", "rtph264depay"), ("dec", "avdec_h264")], [], ("d", "src", "dec", "sink"))
    assert result.allowed
    parser = next(i for i in result.issues if i.rule == "missing-parser")
    assert parser.severity == "warning"
    assert parser.suggestions[0].fix.elements[0].factory == "h264parse"


def test_second_link_from_always_pad_suggests_tee(analyzer):
    result = _check(
        analyzer,
        [("src", "videotestsrc"), ("a", "fakesink"), ("b", "fakesink")],
        [("src", "src", "a", "sink")],
        ("src", "src", "b", "sink"),
    )
    assert not result.allowed
    assert result.issues[0].suggestions[0].fix.kind == "insert_tee"


def test_cycle_is_rejected(analyzer):
    result = _check(
        analyzer,
        [("a", "identity"), ("b", "identity")],
        [("a", "src", "b", "sink")],
        ("b", "src", "a", "sink"),
    )
    assert _rules(result) == {"cycle"}


def test_unknown_pad_is_rejected(analyzer):
    result = _check(analyzer, [("a", "videotestsrc"), ("b", "fakesink")], [], ("a", "nope", "b", "sink"))
    assert _rules(result) == {"unknown-pad"}
