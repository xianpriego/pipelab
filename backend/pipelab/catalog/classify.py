"""Derived classification of elements: family (plugin set) and categories."""

from __future__ import annotations

from pipelab.catalog.models import Family
from pipelab.gst import Gst
from pipelab.gst.caps import media_types as caps_media_types

_SOURCE_FAMILIES: dict[str, Family] = {
    "gstreamer": "core",
    "gst-plugins-base": "base",
    "gst-plugins-good": "good",
    "gst-plugins-bad": "bad",
    "gst-plugins-ugly": "ugly",
    "gst-libav": "libav",
}

_KLASS_TOKENS = {
    "source": "source",
    "src": "source",
    "sink": "sink",
    "encoder": "encoder",
    "decoder": "decoder",
    "parser": "parser",
    "muxer": "muxer",
    "demuxer": "demuxer",
    "payloader": "payloader",
    "depayloader": "depayloader",
    "converter": "converter",
    "scaler": "converter",
    "effect": "effect",
    "filter": "filter",
    "mixer": "mixer",
    "compositor": "mixer",
    "network": "network",
    "rtp": "network",
    "hardware": "hardware",
    "audio": "audio",
    "video": "video",
    "image": "image",
    "text": "text",
    "subtitle": "text",
    "bin": "bin",
    "generic": "generic",
    "analyzer": "analyzer",
    "metadata": "metadata",
}

# Name prefixes of elements that run on GPUs / dedicated hardware.
_HARDWARE_PREFIXES = (
    "nv",
    "cuda",
    "va",
    "vaapi",
    "msdk",
    "qsv",
    "hip",
    "d3d",
    "vulkan",
    "vk",
    "v4l2h",
    "v4l2sl",
    "v4l2jpeg",
    "v4l2mpeg",
    "v4l2vp",
    "amf",
    "mpp",
    "omx",
)


def classify_family(source: str, origin: str) -> Family:
    if "gst-plugins-rs" in origin:
        return "rs"
    return _SOURCE_FAMILIES.get(source, "other")


def classify_categories(name: str, klass: str) -> list[str]:
    tokens = {t.strip().lower() for part in klass.split("/") for t in part.split()}
    categories = {_KLASS_TOKENS[t] for t in tokens if t in _KLASS_TOKENS}
    if name.startswith(_HARDWARE_PREFIXES) and not name.startswith("valve"):
        categories.add("hardware")
    if name.startswith("gl"):
        categories.add("opengl")
    return sorted(categories)


def media_types(caps_string: str) -> list[str]:
    """Media type names (with non-system memory features) in a caps string."""
    caps = Gst.Caps.from_string(caps_string) if caps_string else None
    return caps_media_types(caps) if caps is not None else []


def inferred_any_caps(klass: str, direction: str) -> str | None:
    """Caps implied by the klass of an element whose template says ANY.

    ``autoaudiosink`` or ``fpsdisplaysink`` are bins with ANY templates, but
    their klass ("Sink/Audio", "Sink/Video") tells what they really consume.
    """
    tokens = {t.lower() for t in klass.replace("/", " ").split()}
    role = "sink" if direction == "sink" else "source"
    if role not in tokens or ("audio" in tokens) == ("video" in tokens):
        return None
    return "audio/x-raw(ANY)" if "audio" in tokens else "video/x-raw(ANY)"
