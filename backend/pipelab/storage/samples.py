"""Generates a sample media file so file based templates work out of the box."""

from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

log = logging.getLogger(__name__)

SAMPLE_NAME = "sample.mp4"
_PIPELINE = (
    "videotestsrc num-buffers=300 pattern=smpte ! video/x-raw,width=1280,height=720,framerate=30/1 "
    "! timeoverlay ! videoconvert ! x264enc ! h264parse ! queue ! mp4mux name=mux "
    "! filesink location={location} "
    "audiotestsrc num-buffers=470 wave=ticks ! audio/x-raw,rate=48000,channels=2 ! audioconvert "
    "! avenc_aac ! aacparse ! queue ! mux."
)


def _generate(media_dir: Path) -> None:
    target = media_dir / SAMPLE_NAME
    temporary = media_dir / f".{SAMPLE_NAME}.tmp"
    command = ["gst-launch-1.0", "-q", *_PIPELINE.format(location=temporary).split()]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=120)
        temporary.replace(target)
        log.info("generated %s", target)
    except (subprocess.SubprocessError, OSError) as error:
        log.warning("could not generate the sample media file: %s", error)
        temporary.unlink(missing_ok=True)


def ensure_sample_media(media_dir: Path) -> None:
    if not (media_dir / SAMPLE_NAME).exists():
        threading.Thread(target=_generate, args=(media_dir,), name="sample-media", daemon=True).start()
