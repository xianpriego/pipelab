"""Small helpers on top of Gst.Caps."""

from __future__ import annotations

from functools import lru_cache

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


@lru_cache(maxsize=4096)
def parse_caps(caps_string: str) -> Gst.Caps:
    """Caps from a template or graph string; empty means ANY (cached: do not modify the result)."""
    caps = Gst.Caps.from_string(caps_string) if caps_string else None
    return caps if caps is not None else Gst.Caps.new_any()


@lru_cache(maxsize=4096)
def concrete_caps(caps_string: str) -> Gst.Caps:
    """Template caps without structures whose features are ANY."""
    caps = parse_caps(caps_string)
    if caps.is_any():
        return caps
    result = Gst.Caps.new_empty()
    for index in range(caps.get_size()):
        features = caps.get_features(index)
        if features is not None and features.is_any():
            continue
        result.append_structure_full(caps.get_structure(index).copy(), features.copy() if features else None)
    return result


def media_names(caps: Gst.Caps) -> frozenset[str]:
    """Structure names only (``video/x-raw``), without features."""
    if caps.is_any():
        return frozenset({"ANY"})
    return frozenset(caps.get_structure(i).get_name() for i in range(caps.get_size()))


def has_special_memory(caps: Gst.Caps) -> bool:
    """Whether some structure lives outside system memory (CUDA, GL, DMABuf…)."""
    if caps.is_any():
        return False
    for index in range(caps.get_size()):
        features = caps.get_features(index)
        if features is None or features.is_any():
            continue
        if any(
            features.get_nth(i).startswith("memory:") and features.get_nth(i) != "memory:SystemMemory"
            for i in range(features.get_size())
        ):
            return True
    return False


def caps_to_string(caps: Gst.Caps, limit: int = 4000) -> str:
    text = caps.to_string()
    return text if len(text) <= limit else text[:limit] + "…"


def describe_caps(caps: Gst.Caps, limit: int = 4) -> str:
    """Short human description: the first media types."""
    names = media_types(caps)
    return ", ".join(names[:limit]) + (" …" if len(names) > limit else "")
