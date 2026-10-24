"""Side pipelines that turn media into browser preview frames.

Conversion runs in its own pipeline (``appsrc ! … ! appsink``) so neither its
CPU cost nor its caps constraints ever reach the user's pipeline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pipelab.gst import Gst

AUDIO_RATE = 48000
AUDIO_CHANNELS = 2

FrameHandler = Callable[[dict, bytes], None]
Emit = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class PreviewSettings:
    max_width: int = 960
    max_height: int = 540
    max_fps: int = 15
    jpeg_quality: int = 70


class FrameThinner:
    """Keeps at most ``max_fps`` buffers per second of stream time (by PTS).

    Timestamps of network streams jitter, so a frame is kept when it arrives
    within a quarter of an interval of its slot instead of strictly after it.
    """

    def __init__(self, max_fps: int) -> None:
        self._interval = Gst.SECOND // max_fps
        self._last: int | None = None

    def keep(self, pts: int) -> bool:
        if pts == Gst.CLOCK_TIME_NONE:
            return True
        if self._last is not None and self._last <= pts < self._last + self._interval - self._interval // 4:
            return False
        self._last = pts
        return True


def _buffer_bytes(buffer: Gst.Buffer) -> bytes:
    ok, info = buffer.map(Gst.MapFlags.READ)
    if not ok:
        return b""
    try:
        return bytes(info.data)
    finally:
        buffer.unmap(info)


def sample_handler(
    preview_id: str, kind: str, on_frame: FrameHandler, extra: dict | None = None
) -> Callable[[Gst.Element], Gst.FlowReturn]:
    """``new-sample`` callback that forwards appsink samples as preview frames."""

    def on_sample(sink: Gst.Element) -> Gst.FlowReturn:
        sample = sink.emit("pull-sample")
        header = {"type": "preview", "kind": kind, "node_id": preview_id, **(extra or {})}
        if kind == "video":
            structure = sample.get_caps().get_structure(0)
            header.update(
                mime="image/jpeg", width=structure.get_value("width"), height=structure.get_value("height")
            )
        else:
            header.update(rate=AUDIO_RATE, channels=AUDIO_CHANNELS, format="F32LE")
        on_frame(header, _buffer_bytes(sample.get_buffer()))
        return Gst.FlowReturn.OK

    return on_sample


def _description(kind: str, settings: PreviewSettings, prefix: str, max_buffers: int) -> str:
    head = f"appsrc name=encoder_src format=time leaky-type=downstream max-buffers={max_buffers} ! {prefix}"
    tail = "appsink name=encoder_sink sync=false emit-signals=true max-buffers=2 drop=true"
    if kind == "video":
        caps = (
            f"video/x-raw,format=I420,width=[1,{settings.max_width}],height=[1,{settings.max_height}],"
            "pixel-aspect-ratio=1/1"
        )
        return (
            f"{head}videoconvertscale add-borders=true n-threads=2 ! {caps} "
            f"! jpegenc quality={settings.jpeg_quality} ! {tail}"
        )
    caps = f"audio/x-raw,format=F32LE,rate={AUDIO_RATE},channels={AUDIO_CHANNELS},layout=interleaved"
    return f"{head}audioconvert ! audioresample ! {caps} ! {tail}"


class FrameEncoder:
    """Encodes pushed samples/buffers into preview frames in a separate pipeline."""

    def __init__(
        self,
        kind: str,
        preview_id: str,
        settings: PreviewSettings,
        on_frame: FrameHandler,
        emit: Emit,
        prefix: str = "",
        max_buffers: int = 2,
        extra: dict | None = None,
    ) -> None:
        self.pipeline = Gst.parse_launch(_description(kind, settings, prefix, max_buffers))
        self.source = self.pipeline.get_by_name("encoder_src")
        sink = self.pipeline.get_by_name("encoder_sink")
        sink.connect("new-sample", sample_handler(preview_id, kind, on_frame, extra))
        self._emit = emit
        self._preview_id = preview_id
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_error)
        self.pipeline.set_state(Gst.State.PLAYING)

    def _on_error(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        error, _debug = message.parse_error()
        self._emit(
            {
                "type": "bus",
                "kind": "warning",
                "source": "preview",
                "text": f"Preview {self._preview_id} failed: {error.message}",
            }
        )

    def push_sample(self, sample: Gst.Sample) -> None:
        self.source.emit("push-sample", sample)

    def push_buffer(self, buffer: Gst.Buffer) -> None:
        self.source.emit("push-buffer", buffer)

    def close(self) -> None:
        self.pipeline.set_state(Gst.State.NULL)
