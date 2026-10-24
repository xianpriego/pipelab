"""Human hints for the most common GStreamer runtime errors."""

from __future__ import annotations

from pipelab.gst import GLib, Gst

_DEBUG_HINTS = [
    (
        "not-negotiated",
        "Caps negotiation failed: the elements around this link cannot agree on a format. "
        "Insert a converter (videoconvert, videoscale, audioconvert, audioresample) or relax the "
        "capsfilter; the Issues tab lists concrete suggestions.",
    ),
    (
        "not-linked",
        "Data reached a pad without peer: a demuxer/decoder exposed a stream nobody consumes or "
        "a dynamic pad could not be linked. Link every output (or end it in a fakesink).",
    ),
    ("reason error", "An element upstream failed first: look at the earlier error messages."),
    (
        "CUDA",
        "CUDA/NVENC is not available: start Pipelab with the GPU override "
        "(make up GPU=1) and check the NVIDIA driver and container toolkit.",
    ),
    (
        "nvenc",
        "NVENC session failed: the GPU may be busy, unsupported for this codec or not exposed to "
        "the container (make up GPU=1).",
    ),
    (
        "Could not open audio device",
        "There is no sound card in the container; use autoaudiosink so the browser preview replaces it.",
    ),
]

_RESOURCE_HINTS = {
    Gst.ResourceError.NOT_FOUND: "File or device not found: check location/uri. Relative paths are "
    "resolved inside /data/media (the Outputs tab).",
    Gst.ResourceError.OPEN_READ: "Cannot open for reading: check the path/uri and permissions.",
    Gst.ResourceError.OPEN_WRITE: "Cannot open for writing: does the directory exist inside /data/media?",
    Gst.ResourceError.BUSY: "The device is busy: another process or pipeline is using it.",
    Gst.ResourceError.SETTINGS: "The element rejected its settings: review its properties.",
}

_STREAM_HINTS = {
    Gst.StreamError.DECODE: "The stream could not be decoded: it may be corrupt or need a parser before "
    "the decoder.",
    Gst.StreamError.TYPE_NOT_FOUND: "The stream type could not be detected (typefind failed).",
    Gst.StreamError.CODEC_NOT_FOUND: "No decoder/demuxer installed for this format.",
    Gst.StreamError.FORMAT: "Unexpected stream format: check caps and parsers.",
}


def hint_for(error: GLib.Error, debug: str | None) -> str | None:
    debug = debug or ""
    if error.domain == "gst-resource-error-quark":
        hint = _RESOURCE_HINTS.get(Gst.ResourceError(error.code))
        if hint:
            return hint
    if error.domain == "gst-stream-error-quark":
        if error.code == Gst.StreamError.FAILED or "not-negotiated" in debug or "not-linked" in debug:
            return next((h for k, h in _DEBUG_HINTS if k in debug), None)
        hint = _STREAM_HINTS.get(Gst.StreamError(error.code))
        if hint:
            return hint
    if error.domain == "gst-core-error-quark" and error.code == Gst.CoreError.MISSING_PLUGIN:
        return "A required plugin is missing in this GStreamer installation."
    text = f"{error.message} {debug}"
    return next((hint for key, hint in _DEBUG_HINTS if key in text), None)
