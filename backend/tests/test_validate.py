from pipelab.graph.validate import validate_graph
from tests.helpers import chain, graph


def _rules(analyzer, g):
    return {issue.rule: issue for issue in validate_graph(analyzer, g)}


def test_clean_pipeline_has_no_errors(analyzer):
    g = chain(
        ("videotestsrc", {"is-live": True}),
        ("capsfilter", {"caps": "video/x-raw,width=320,height=240"}),
        "videoconvert",
        "autovideosink",
    )
    issues = validate_graph(analyzer, g)
    assert [i for i in issues if i.severity == "error"] == []


def test_missing_element_and_endpoints(analyzer):
    rules = _rules(analyzer, chain("doesnotexist", "videoconvert"))
    assert "missing-element" in rules
    assert "no-source" in rules and "no-sink" in rules


def test_invalid_property_values(analyzer):
    g = chain(("videotestsrc", {"pattern": "nonsense", "num-buffers": "abc", "bogus": 1}), "fakesink")
    messages = [i.message for i in validate_graph(analyzer, g) if i.rule == "invalid-property"]
    assert len(messages) == 3


def test_required_location(analyzer):
    rules = _rules(analyzer, chain("filesrc", "fakesink"))
    assert "required-property" in rules


def test_unlinked_pads(analyzer):
    g = graph([("src", "videotestsrc"), ("conv", "videoconvert")], [("src", "src", "conv", "sink")])
    issue = _rules(analyzer, g)["unlinked-pad"]
    assert issue.node_ids == ["conv"]


def test_tee_branches_without_queue(analyzer):
    g = graph(
        [("src", "videotestsrc"), ("t", "tee"), ("a", "fakesink"), ("q", "queue"), ("b", "fakesink")],
        [
            ("src", "src", "t", "sink"),
            ("t", "src_0", "a", "sink"),
            ("t", "src_1", "q", "sink"),
            ("q", "src", "b", "sink"),
        ],
    )
    issue = _rules(analyzer, g)["tee-queue"]
    assert issue.edge_ids == ["e1"]
    assert issue.suggestions[0].fix.kind == "insert_on_edge"


def test_demuxer_branches_and_parser(analyzer):
    g = graph(
        [
            ("f", "filesrc", {"location": "a.mp4"}),
            ("d", "qtdemux"),
            ("v", "avdec_h264"),
            ("vs", "fakesink"),
            ("a", "avdec_aac"),
            ("as", "fakesink"),
        ],
        [
            ("f", "src", "d", "sink"),
            ("d", "video_%u", "v", "sink"),
            ("v", "src", "vs", "sink"),
            ("d", "audio_%u", "a", "sink"),
            ("a", "src", "as", "sink"),
        ],
    )
    rules = _rules(analyzer, g)
    assert "demuxer-queue" in rules
    assert not [i for i in validate_graph(analyzer, g) if i.severity == "error"]


def test_streaming_suggestions(analyzer):
    g = chain("videotestsrc", "videoconvert", "x264enc", "rtph264pay", ("udpsink", {"host": "127.0.0.1"}))
    rules = _rules(analyzer, g)
    assert rules["encoder-latency"].suggestions[0].fix.value == "zerolatency"
    assert rules["rtp-config-interval"].suggestions[0].fix.value == -1
    assert "source-caps" in rules


def test_loopback_in_one_pipeline_needs_async_false(analyzer):
    g = graph(
        [("src", "audiotestsrc"), ("tx", "udpsink"), ("rx", "udpsrc"), ("sink", "fakesink")],
        [("src", "src", "tx", "sink"), ("rx", "src", "sink", "sink")],
    )
    issue = _rules(analyzer, g)["loopback-async"]
    assert issue.node_ids == ["tx"] and issue.suggestions[0].fix.value is False
    g.nodes[1].properties["async"] = False
    assert "loopback-async" not in _rules(analyzer, g)
