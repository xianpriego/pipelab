"""Starter pipelines offered when creating a project.

They are written as gst-launch descriptions and turned into graphs with the
importer, so they double as living documentation of idiomatic pipelines.
Relative file names resolve inside the media directory (/data/media).
"""

from __future__ import annotations

from dataclasses import dataclass

VIDEO_720P = "video/x-raw,width=1280,height=720,framerate=30/1"
RTP_H264_CAPS = "application/x-rtp,media=video,encoding-name=H264,clock-rate=90000,payload=96"


@dataclass(frozen=True)
class Starter:
    id: str
    name: str
    description: str
    pipeline: str


STARTERS: list[Starter] = [
    Starter(
        "video-test",
        "Video test pattern",
        "Live test pattern with a clock overlay, previewed in the browser.",
        f"videotestsrc is-live=true pattern=ball ! {VIDEO_720P} ! timeoverlay ! videoconvert ! autovideosink",
    ),
    Starter(
        "audio-test",
        "Audio test tone",
        "440 Hz sine wave; listen to it from the Preview tab.",
        "audiotestsrc is-live=true wave=sine freq=440 volume=0.4 ! audio/x-raw,rate=48000,channels=2 "
        "! audioconvert ! audioresample ! autoaudiosink",
    ),
    Starter(
        "record-mp4",
        "Encode to MP4",
        "Encodes 10 s of H.264 into test.mp4 (see the Outputs tab).",
        f"videotestsrc num-buffers=300 ! {VIDEO_720P} ! videoconvert ! x264enc tune=zerolatency "
        "! h264parse ! mp4mux ! filesink location=test.mp4",
    ),
    Starter(
        "tee-preview-record",
        "Preview + record (tee)",
        "Splits a live stream with a tee: one branch is previewed, the other recorded.",
        f"videotestsrc is-live=true ! {VIDEO_720P} ! tee name=t "
        "t. ! queue ! videoconvert ! autovideosink "
        "t. ! queue ! videoconvert ! x264enc tune=zerolatency ! h264parse "
        "! mp4mux fragment-duration=1000 ! filesink location=recording.mp4",
    ),
    Starter(
        "input-selector",
        "Input selector",
        "Two sources into an input-selector: switch active-pad live from the inspector.",
        "input-selector name=sel ! videoconvert ! autovideosink "
        "videotestsrc is-live=true pattern=smpte ! video/x-raw,width=640,height=360,framerate=30/1 "
        "! sel.sink_0 "
        "videotestsrc is-live=true pattern=ball ! video/x-raw,width=640,height=360,framerate=30/1 "
        "! sel.sink_1",
    ),
    Starter(
        "compositor-pip",
        "Picture in picture",
        "compositor mixing two sources; move the small one with sink_1 pad properties.",
        "compositor name=mix sink_1::xpos=920 sink_1::ypos=520 ! videoconvert ! autovideosink "
        f"videotestsrc is-live=true ! {VIDEO_720P} ! queue ! mix.sink_0 "
        "videotestsrc is-live=true pattern=ball ! video/x-raw,width=320,height=180,framerate=30/1 "
        "! queue ! mix.sink_1",
    ),
    Starter(
        "rtp-loopback",
        "RTP/UDP loopback",
        "Sends H.264 over RTP to 127.0.0.1:5000 and receives it back in the same pipeline "
        "(async=false on udpsink avoids the preroll deadlock of in-pipeline loopbacks).",
        "videotestsrc is-live=true ! video/x-raw,width=640,height=360,framerate=30/1 ! videoconvert "
        "! x264enc tune=zerolatency key-int-max=30 ! rtph264pay config-interval=-1 "
        "! udpsink host=127.0.0.1 port=5000 async=false "
        f'udpsrc port=5000 caps="{RTP_H264_CAPS}" '
        "! rtpjitterbuffer ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink",
    ),
    Starter(
        "decode-file",
        "Play a media file",
        "Decodes sample.mp4 (generated at start-up) with decodebin into video and audio branches.",
        "filesrc location=sample.mp4 ! decodebin name=dec "
        "dec. ! queue ! videoconvert ! autovideosink "
        "dec. ! queue ! audioconvert ! audioresample ! autoaudiosink",
    ),
    Starter(
        "hls",
        "HLS output",
        "Writes an HLS playlist (playlist.m3u8) playable from the Outputs tab.",
        f"videotestsrc is-live=true ! {VIDEO_720P} ! videoconvert ! x264enc tune=zerolatency "
        "key-int-max=60 ! h264parse ! hlssink2 location=segment%05d.ts playlist-location=playlist.m3u8 "
        "target-duration=2 max-files=10",
    ),
    Starter(
        "audio-analysis",
        "Audio level and spectrum",
        "level and spectrum post element messages on the bus (see the Bus tab).",
        "audiotestsrc is-live=true wave=pink-noise volume=0.3 ! audioconvert "
        "! level interval=200000000 ! spectrum bands=32 interval=200000000 ! audioconvert "
        "! autoaudiosink",
    ),
    Starter(
        "nvidia-transcode",
        "NVIDIA encode/decode",
        "NVENC H.264 encode and NVDEC decode on the GPU (needs the GPU compose override).",
        "videotestsrc is-live=true ! video/x-raw,width=1920,height=1080,framerate=30/1 ! cudaupload "
        "! nvh264enc ! h264parse ! nvh264dec ! cudadownload ! videoconvert ! autovideosink",
    ),
]
