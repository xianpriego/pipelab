from pipelab.graph.fixes import apply_fix
from pipelab.graph.models import Fix, FixElement, PadRef
from pipelab.graph.validate import validate_graph
from tests.helpers import chain, graph, named_links


def _links(g):
    return sorted(
        f"{source}.{src_pad}->{target}.{sink_pad}" for source, src_pad, target, sink_pad in named_links(g)
    )


def test_insert_on_edge_creates_chain(analyzer):
    g = chain("videotestsrc", "x264enc")
    fixed = apply_fix(
        analyzer, g, Fix(kind="insert_on_edge", edge_id="e0", elements=[FixElement(factory="videoconvert")])
    )
    assert _links(fixed) == ["videoconvert0.src->x264enc1.sink", "videotestsrc0.src->videoconvert0.sink"]


def test_connect_via_resolves_request_pads(analyzer):
    g = graph([("src", "videotestsrc"), ("mux", "mp4mux")], [])
    fix = Fix(
        kind="connect_via",
        source=PadRef(node_id="src", pad="src"),
        target=PadRef(node_id="mux", pad="video_%u"),
        elements=[FixElement(factory="x264enc"), FixElement(factory="h264parse")],
    )
    fixed = apply_fix(analyzer, g, fix)
    assert "h264parse0.src->mux.video_0" in _links(fixed)


def test_insert_tee_adds_queues(analyzer):
    g = graph([("src", "videotestsrc"), ("a", "fakesink"), ("b", "fakesink")], [("src", "src", "a", "sink")])
    fix = Fix(
        kind="insert_tee",
        edge_ids=["e0"],
        source=PadRef(node_id="src", pad="src"),
        target=PadRef(node_id="b", pad="sink"),
    )
    fixed = apply_fix(analyzer, g, fix)
    assert _links(fixed) == [
        "queue0.src->a.sink",
        "queue1.src->b.sink",
        "src.src->tee0.sink",
        "tee0.src_0->queue0.sink",
        "tee0.src_1->queue1.sink",
    ]
    assert not [i for i in validate_graph(analyzer, fixed) if i.rule == "tee-queue"]


def test_applying_suggested_fix_clears_the_issue(analyzer):
    g = graph(
        [("src", "videotestsrc"), ("t", "tee"), ("a", "fakesink"), ("b", "fakesink")],
        [("src", "src", "t", "sink"), ("t", "src_0", "a", "sink"), ("t", "src_1", "b", "sink")],
    )
    issue = next(i for i in validate_graph(analyzer, g) if i.rule == "tee-queue")
    fixed = apply_fix(analyzer, g, issue.suggestions[0].fix)
    assert not [i for i in validate_graph(analyzer, fixed) if i.rule == "tee-queue"]


def test_set_property(analyzer):
    g = chain("x264enc", "fakesink")
    fixed = apply_fix(
        analyzer, g, Fix(kind="set_property", node_id="n0", property="tune", value="zerolatency")
    )
    assert fixed.nodes[0].properties == {"tune": "zerolatency"}
    assert g.nodes[0].properties == {}


def test_connect_via_resolves_request_source_pads(analyzer):
    g = graph([("src", "videotestsrc"), ("t", "tee"), ("sink", "fakesink")], [("src", "src", "t", "sink")])
    fix = Fix(
        kind="connect_via",
        source=PadRef(node_id="t", pad="src_%u"),
        target=PadRef(node_id="sink", pad="sink"),
        elements=[FixElement(factory="queue")],
    )
    assert "t.src_0->queue0.sink" in _links(apply_fix(analyzer, g, fix))
