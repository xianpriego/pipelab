"""Starter components: everyday building blocks offered for installation into the library.

Like the project templates they are gst-launch descriptions resolved against the catalog of this
machine (so elements that are not installed, e.g. NVIDIA ones without a GPU, are reported).
Ports and parameters refer to elements by their ``name=``. Installing copies the definition into the
library, where it is an ordinary component (editable, deletable).
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from pipelab.catalog.store import Catalog
from pipelab.components.models import Component, ComponentParam, ComponentPort, ParamTarget
from pipelab.graph.models import Graph
from pipelab.importer.gst_launch import import_gst_launch

_X264 = "x264enc name=enc tune=zerolatency speed-preset=veryfast bitrate=4000 key-int-max=60"
_BITRATE = ("bitrate", "Encoder bitrate in kbit/s", (("enc", "bitrate"),))
_KEYFRAMES = ("keyframe-interval", "Frames between keyframes", (("enc", "key-int-max"),))
_RTSP = (
    ("location", "RTSP URL (rtsp://user:password@host:port/path)", (("src", "location"),)),
    ("latency", "Jitter buffer in ms", (("src", "latency"),)),
)


@dataclass(frozen=True)
class StarterComponent:
    id: str
    name: str
    description: str
    pipeline: str
    ports: tuple[tuple[str, str, str, str], ...]  # (port, direction src|sink, element name, pad)
    params: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = ()  # (name, description, targets)


def _rtsp_input(codec: str, decoder: str, name: str, description: str, suffix: str = "") -> StarterComponent:
    return StarterComponent(
        f"rtsp-{codec}-input{suffix}",
        name,
        description,
        f"rtspsrc name=src location=rtsp://127.0.0.1:8554/stream latency=200 ! rtp{codec}depay "
        f"! {codec}parse ! {decoder} ! videoconvert name=out",
        (("src", "src", "out", "src"),),
        _RTSP,
    )


STARTER_COMPONENTS: list[StarterComponent] = [
    _rtsp_input(
        "h264", "avdec_h264", "RTSP H.264 input", "RTSP camera with H.264, decoded on the CPU: raw video out."
    ),
    _rtsp_input(
        "h264",
        "nvh264dec",
        "RTSP H.264 input (NVIDIA)",
        "RTSP camera with H.264 decoded on the GPU (NVDEC, up to 4096 px wide): raw video out.",
        "-nvidia",
    ),
    _rtsp_input("h265", "avdec_h265", "RTSP H.265 input", "RTSP camera with H.265/HEVC, decoded on the CPU."),
    _rtsp_input(
        "h265",
        "nvh265dec",
        "RTSP H.265 input (NVIDIA)",
        "RTSP camera with H.265/HEVC decoded on the GPU (NVDEC): raw video out.",
        "-nvidia",
    ),
    StarterComponent(
        "file-video-input",
        "File video input",
        "Any media file (relative paths are in the media folder), decoded: raw video out.",
        "filesrc name=src location=sample.mp4 ! decodebin ! videoconvert name=out",
        (("src", "src", "out", "src"),),
        (("location", "File to play", (("src", "location"),)),),
    ),
    StarterComponent(
        "video-scaler",
        "Video scaler",
        "Converts and scales raw video to a fixed format (edit the caps parameter).",
        "videoconvert name=in ! videoscale ! capsfilter name=caps caps=video/x-raw,width=1280,height=720",
        (("sink", "sink", "in", "sink"), ("src", "src", "caps", "src")),
        (("caps", "Output caps, e.g. video/x-raw,width=640,height=360", (("caps", "caps"),)),),
    ),
    StarterComponent(
        "h264-encoder",
        "H.264 encoder",
        "Raw video in, H.264 byte-stream out (x264, low latency).",
        f"videoconvert name=in ! {_X264} ! h264parse name=out config-interval=-1",
        (("sink", "sink", "in", "sink"), ("src", "src", "out", "src")),
        (_BITRATE, _KEYFRAMES),
    ),
    StarterComponent(
        "h264-encoder-nvidia",
        "H.264 encoder (NVIDIA)",
        "Raw video in, H.264 out, encoded on the GPU (NVENC).",
        "videoconvert name=in ! nvh264enc name=enc bitrate=4000 gop-size=60 "
        "! h264parse name=out config-interval=-1",
        (("sink", "sink", "in", "sink"), ("src", "src", "out", "src")),
        (_BITRATE, ("keyframe-interval", "Frames between keyframes", (("enc", "gop-size"),))),
    ),
    StarterComponent(
        "mp4-recorder",
        "MP4 recorder",
        "Raw video in; records H.264 MP4 files split in segments (stop with EOS to close the last one).",
        f"queue name=in ! videoconvert ! {_X264} ! h264parse ! splitmuxsink name=mux "
        "location=recording-%05d.mp4 max-size-time=60000000000",
        (("sink", "sink", "in", "sink"),),
        (
            ("location", "File pattern (%05d = segment number)", (("mux", "location"),)),
            ("segment-duration", "Segment length in ns (0 = one file)", (("mux", "max-size-time"),)),
            _BITRATE,
        ),
    ),
    StarterComponent(
        "srt-output",
        "SRT output",
        "Raw video in; H.264 in MPEG-TS over SRT (listener on port 8888 by default).",
        f"queue name=in ! videoconvert ! {_X264} ! h264parse config-interval=-1 ! mpegtsmux "
        "! srtsink name=out uri=srt://:8888 wait-for-connection=false",
        (("sink", "sink", "in", "sink"),),
        (("uri", "srt://host:port (caller) or srt://:port (listener)", (("out", "uri"),)), _BITRATE),
    ),
    StarterComponent(
        "rtmp-output",
        "RTMP output",
        "Raw video in; H.264 in FLV pushed to an RTMP server.",
        f"queue name=in ! videoconvert ! {_X264} ! h264parse ! flvmux streamable=true "
        "! rtmp2sink name=out location=rtmp://127.0.0.1/live/stream",
        (("sink", "sink", "in", "sink"),),
        (("location", "rtmp://server/app/stream", (("out", "location"),)), _BITRATE),
    ),
    StarterComponent(
        "rtp-udp-output",
        "RTP/UDP output",
        "Raw video in; H.264 RTP packets sent over UDP (payload 96).",
        f"queue name=in ! videoconvert ! {_X264} ! rtph264pay config-interval=1 pt=96 "
        "! udpsink name=out host=127.0.0.1 port=5000",
        (("sink", "sink", "in", "sink"),),
        (
            ("host", "Destination host", (("out", "host"),)),
            ("port", "Destination UDP port", (("out", "port"),)),
            _BITRATE,
        ),
    ),
    StarterComponent(
        "display",
        "Display",
        "Shows raw video without slowing the branch down (a leaky queue drops late frames).",
        "queue name=in leaky=downstream max-size-buffers=2 ! videoconvert ! autovideosink",
        (("sink", "sink", "in", "sink"),),
    ),
]


class StarterInfo(BaseModel):
    id: str
    name: str
    description: str
    available: bool
    missing: list[str] = Field(default_factory=list)


class StarterNotFound(KeyError):
    pass


def _definition(starter: StarterComponent, catalog: Catalog) -> Component:
    graph: Graph = import_gst_launch(starter.pipeline, catalog).graph
    by_name = {node.name: node.id for node in graph.nodes}
    ports = [
        ComponentPort(name=port, direction=direction, node_id=by_name[element], pad=pad)
        for port, direction, element, pad in starter.ports
    ]
    params = [
        ComponentParam(
            name=name,
            description=description,
            targets=[ParamTarget(node_id=by_name[element], property=prop) for element, prop in targets],
        )
        for name, description, targets in starter.params
    ]
    return Component(
        id=starter.id,
        name=starter.name,
        description=starter.description,
        graph=graph,
        ports=ports,
        parameters=params,
    )


class StarterComponents:
    def __init__(self, catalog: Catalog) -> None:
        self._catalog = catalog
        self._definitions: dict[str, Component] = {}

    def definition(self, starter_id: str) -> Component:
        starter = next((s for s in STARTER_COMPONENTS if s.id == starter_id), None)
        if starter is None:
            raise StarterNotFound(starter_id)
        if starter_id not in self._definitions:
            self._definitions[starter_id] = _definition(starter, self._catalog)
        return self._definitions[starter_id].model_copy(deep=True)

    def list(self) -> list[StarterInfo]:
        infos = []
        for starter in STARTER_COMPONENTS:
            graph = self.definition(starter.id).graph
            missing = sorted({node.factory for node in graph.nodes if node.factory not in self._catalog})
            infos.append(
                StarterInfo(
                    id=starter.id,
                    name=starter.name,
                    description=starter.description,
                    available=not missing,
                    missing=missing,
                )
            )
        return infos
