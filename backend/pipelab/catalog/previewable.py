"""Sinks that the runtime replaces by a browser preview (shared with the worker)."""

from __future__ import annotations

from typing import Literal

PreviewKind = Literal["video", "audio"]

VIDEO_SINKS = frozenset(
    {
        "autovideosink",
        "xvimagesink",
        "ximagesink",
        "glimagesink",
        "glimagesinkelement",
        "gtksink",
        "gtkglsink",
        "gtkwaylandsink",
        "gtk4paintablesink",
        "waylandsink",
        "kmssink",
        "fbdevsink",
        "fpsdisplaysink",
        "nveglglessink",
        "clutterautovideosink",
        "qmlglsink",
        "qml6glsink",
        "vulkansink",
        "glsinkbin",
        "aasink",
        "cacasink",
        "d3d11videosink",
        "d3d12videosink",
        "osxvideosink",
        "sdlvideosink",
        "directfbvideosink",
    }
)
AUDIO_SINKS = frozenset(
    {
        "autoaudiosink",
        "pulsesink",
        "alsasink",
        "jackaudiosink",
        "openalsink",
        "osssink",
        "oss4sink",
        "directsoundsink",
        "wasapisink",
        "wasapi2sink",
        "osxaudiosink",
        "sdlaudiosink",
    }
)


def preview_kind_for(factory: str) -> PreviewKind | None:
    if factory in VIDEO_SINKS:
        return "video"
    if factory in AUDIO_SINKS:
        return "audio"
    return None
