from pipelab.graph.bridge import concrete_caps
from pipelab.graph.caps_flow import CapsFlow
from pipelab.gst import Gst
from tests.helpers import chain, graph


def _names(caps):
    return {caps.get_structure(i).get_name() for i in range(caps.get_size())}


def test_passthrough_elements_forward_upstream_caps(catalog):
    g = chain("x264enc", "queue", "tee", "fakesink", pads={2: ("src_0", "sink")})
    flow = CapsFlow(g, catalog)
    assert _names(flow.output_caps("n2", "src_0")) == {"video/x-h264"}


def test_capsfilter_narrows_caps(catalog):
    g = chain("videotestsrc", ("capsfilter", {"caps": "video/x-raw,format=NV12,width=640"}), "fakesink")
    caps = CapsFlow(g, catalog).output_caps("n1", "src")
    assert caps.get_structure(0).get_value("format") == "NV12"
    assert caps.get_structure(0).get_value("width") == 640


def test_source_caps_property_constrains_output(catalog):
    g = chain(("udpsrc", {"caps": "application/x-rtp,media=video"}), "fakesink")
    assert _names(CapsFlow(g, catalog).output_caps("n0", "src")) == {"application/x-rtp"}


def test_any_sinks_are_inferred_from_their_klass(catalog):
    g = chain("audiotestsrc", "autoaudiosink")
    caps = CapsFlow(g, catalog).input_caps("n1", "sink")
    assert _names(caps) == {"audio/x-raw"}


def test_multiqueue_maps_pads_by_index(catalog):
    g = graph(
        [("v", "x264enc"), ("a", "opusenc"), ("mq", "multiqueue")],
        [("v", "src", "mq", "sink_0"), ("a", "src", "mq", "sink_1")],
    )
    flow = CapsFlow(g, catalog)
    assert _names(flow.output_caps("mq", "src_0")) == {"video/x-h264"}
    assert _names(flow.output_caps("mq", "src_1")) == {"audio/x-opus"}


def test_concrete_caps_drops_any_features():
    caps = concrete_caps("video/x-raw(ANY); video/x-raw, format=I420")
    assert caps.get_size() == 1
    assert not caps.get_features(0).is_any()


def test_bridge_prefers_idiomatic_converters(analyzer):
    src = Gst.Caps.from_string("video/x-raw,format=RGB,width=640,height=480")
    sink = Gst.Caps.from_string("video/x-raw,format=NV12,width=640,height=480")
    assert analyzer.bridges.find(src, sink)[0] == ["videoconvert"]
    audio_src = Gst.Caps.from_string("audio/x-raw,format=S16LE,rate=44100,channels=2")
    audio_sink = Gst.Caps.from_string("audio/x-raw,format=F32LE,rate=48000,channels=2")
    assert analyzer.bridges.find(audio_src, audio_sink)[0] in (["audioconvert"], ["audioresample"])
