"""Small helpers on top of Gst.Caps."""

from __future__ import annotations

from pipelab.gst import Gst


def media_types(caps: Gst.Caps) -> list[str]:
    """Media types with their non-system memory features, e.g. ``video/x-raw(memory:CUDAMemory)``."""
    if caps.is_any():
        return ["ANY"]
    names: list[str] = []
    for index in range(caps.get_size()):
        name = caps.get_structure(index).get_name()
        features = caps.get_features(index)
        if features is not None and features.is_any():
            name = f"{name}(ANY)"
        elif features is not None:
            extra = [features.get_nth(i) for i in range(features.get_size())]
            extra = [f for f in extra if f != "memory:SystemMemory"]
            if extra:
                name = f"{name}({','.join(extra)})"
        if name not in names:
            names.append(name)
    return names


def parse_structure(text: str) -> Gst.Structure | None:
    try:
        return Gst.Structure.new_from_string(text)
    except TypeError:
        return None
