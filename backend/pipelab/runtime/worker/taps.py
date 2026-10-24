"""Link taps: preview what flows through any link of a running pipeline.

A pad probe copies buffers from the link into a ``FrameEncoder`` side pipeline
(decoding first when the link carries encoded media) so watching a link never
changes the negotiation or the timing of the user's pipeline.
"""

from __future__ import annotations

from pipelab.gst import Gst
from pipelab.runtime.worker.encoder import Emit, FrameEncoder, FrameHandler, FrameThinner, PreviewSettings

_DOWNLOADERS = {"memory:CUDAMemory": "cudadownload ! ", "memory:GLMemory": "gldownload ! "}
# Encoded streams cannot lose buffers without corrupting the decode.
_ENCODED_QUEUE = 300


def _family(caps: Gst.Caps) -> str | None:
    structure = caps.get_structure(0)
    name = structure.get_name()
    if name == "application/x-rtp":
        name = f"{structure.get_string('media') or ''}/rtp"
    if name.startswith(("video/", "image/")):
        return "video"
    if name.startswith("audio/"):
        return "audio"
    return None


def _download(caps: Gst.Caps) -> str:
    features = caps.get_features(0)
    if features is None:
        return ""
    return "".join(_DOWNLOADERS.get(features.get_nth(i), "") for i in range(features.get_size()))


class LinkTap:
    def __init__(
        self, edge_id: str, pad: Gst.Pad, settings: PreviewSettings, on_frame: FrameHandler, emit: Emit
    ) -> None:
        caps = pad.get_current_caps()
        if caps is None or caps.is_empty():
            raise ValueError("the link has not negotiated caps yet")
        family = _family(caps)
        if family is None:
            raise ValueError(f"cannot preview {caps.get_structure(0).get_name()} data")
        raw = caps.get_structure(0).get_name() in ("video/x-raw", "audio/x-raw")
        self._encoder = FrameEncoder(
            family,
            f"edge:{edge_id}",
            settings,
            on_frame,
            emit,
            prefix=_download(caps) if raw else "decodebin ! ",
            max_buffers=2 if raw else _ENCODED_QUEUE,
            extra={"edge_id": edge_id},
        )
        self._encoder.source.set_property("caps", caps)
        thinner = FrameThinner(settings.max_fps) if raw and family == "video" else None

        def copy(_pad: Gst.Pad, info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
            buffer = info.get_buffer()
            if thinner is None or thinner.keep(buffer.pts):
                self._encoder.push_buffer(buffer)
            return Gst.PadProbeReturn.OK

        self._pad = pad
        self._probe = pad.add_probe(Gst.PadProbeType.BUFFER, copy)

    def close(self) -> None:
        self._pad.remove_probe(self._probe)
        self._encoder.close()
