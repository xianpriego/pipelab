"""Browser previews: display and audio sinks are replaced by an appsink.

A container has no display or sound card, so ``autovideosink`` & co. become an
``appsink`` with the same name (bus messages still point at the user's node)
and the same ``sync``, which paces the pipeline exactly like the real sink.
Its caps only express a preference for common formats (never sizes or rates) so
negotiation is not steered; samples are handed to a ``FrameEncoder`` side
pipeline for scaling and JPEG/PCM output.
"""

from __future__ import annotations

from pipelab.catalog.previewable import preview_kind_for
from pipelab.graph.models import Node
from pipelab.gst import Gst
from pipelab.runtime.worker.encoder import Emit, FrameEncoder, FrameHandler, FrameThinner, PreviewSettings

# Raw buffers waiting for the encoder; beyond that, previews drop frames.
_ENCODER_QUEUE = {"video": 2, "audio": 100}
# What a real display/audio sink would prefer, without forbidding anything else:
# unconstrained caps make sources fixate to their first (often exotic) format.
# One structure per format, because only the order of structures is a preference.
_VIDEO_FORMATS = ("I420", "NV12", "YUY2", "UYVY", "BGRx", "RGBx", "BGRA", "RGBA", "RGB", "BGR", "GRAY8")
_AUDIO_FORMATS = ("S16LE", "F32LE", "S32LE")
_SINK_CAPS = {
    "video": "; ".join([*(f"video/x-raw, format={f}" for f in _VIDEO_FORMATS), "video/x-raw"]),
    "audio": "; ".join(
        [*(f"audio/x-raw, format={f}, layout=interleaved" for f in _AUDIO_FORMATS), "audio/x-raw"]
    ),
}


def preview_kind(node: Node) -> str | None:
    return None if node.preview == "off" else preview_kind_for(node.factory)


def _sync(node: Node) -> bool:
    value = node.properties.get("sync", True)
    return value if isinstance(value, bool) else str(value).lower() not in ("false", "0", "no")


def preview_sink(
    node: Node, kind: str, settings: PreviewSettings, on_frame: FrameHandler, emit: Emit
) -> tuple[Gst.Element, FrameEncoder]:
    """The element replacing ``node`` and the side pipeline encoding its frames."""
    encoder = FrameEncoder(kind, node.id, settings, on_frame, emit, max_buffers=_ENCODER_QUEUE[kind])
    sink = Gst.ElementFactory.make("appsink", node.name)
    sink.set_property("caps", Gst.Caps.from_string(_SINK_CAPS[kind]))
    sink.set_property("sync", _sync(node))
    sink.set_property("emit-signals", True)
    sink.set_property("max-buffers", 1)
    thinner = FrameThinner(settings.max_fps) if kind == "video" else None

    def on_sample(appsink: Gst.Element) -> Gst.FlowReturn:
        sample = appsink.emit("pull-sample")
        if thinner is None or thinner.keep(sample.get_buffer().pts):
            encoder.push_sample(sample)
        return Gst.FlowReturn.OK

    sink.connect("new-sample", on_sample)
    return sink, encoder
