"""Finds element chains that convert between two incompatible caps.

Given the caps produced upstream and the caps accepted downstream it searches
the catalog for one or two "transforming" elements (converters, parsers,
decoders, encoders, (de)payloaders, memory up/downloaders) whose templates
connect both sides, and ranks them so the idiomatic choice comes first.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipelab.catalog.models import ElementInfo
from pipelab.catalog.store import Catalog
from pipelab.gst import Gst
from pipelab.gst.caps import concrete_caps, has_special_memory, media_names

TRANSFORMING = {"converter", "parser", "decoder", "encoder", "payloader", "depayloader"}
_MEMORY_SUFFIXES = ("upload", "download", "convert", "scale", "postproc")

# Idiomatic elements get a bonus so they are suggested first.
PREFERRED = {
    "videoconvert": 4,
    "audioconvert": 4,
    "audioresample": 3,
    "videoscale": 3,
    "videorate": 2,
    "audiorate": 1,
    "h264parse": 4,
    "h265parse": 4,
    "h266parse": 3,
    "av1parse": 4,
    "vp9parse": 3,
    "mpegvideoparse": 3,
    "mpeg4videoparse": 3,
    "aacparse": 4,
    "mpegaudioparse": 4,
    "opusparse": 3,
    "jpegparse": 3,
    "flacparse": 3,
    "ac3parse": 3,
    "x264enc": 3,
    "x265enc": 2,
    "avdec_h264": 3,
    "avdec_h265": 3,
    "opusenc": 3,
    "opusdec": 3,
    "avenc_aac": 2,
    "fdkaacenc": 1,
    "jpegenc": 3,
    "jpegdec": 3,
    "pngenc": 2,
    "vp8enc": 2,
    "vp8dec": 2,
    "vp9dec": 2,
    "cudaupload": 3,
    "cudadownload": 3,
    "glupload": 2,
    "gldownload": 2,
    "rtph264pay": 3,
    "rtph264depay": 3,
    "rtph265pay": 3,
    "rtph265depay": 3,
    "rtpopuspay": 3,
    "rtpopusdepay": 3,
    "decodebin": 0,
    "rawaudioparse": 1,
}
_RANK_COST = ((Gst.Rank.PRIMARY, 0), (Gst.Rank.SECONDARY, 1), (Gst.Rank.MARGINAL, 2))


@dataclass(frozen=True)
class _Candidate:
    element: ElementInfo
    sink: Gst.Caps
    src: Gst.Caps
    sink_types: frozenset[str]
    src_types: frozenset[str]


def _is_transforming(element: ElementInfo) -> bool:
    if "source" in element.categories or "sink" in element.categories:
        return False
    if TRANSFORMING & set(element.categories):
        return True
    return element.name.endswith(_MEMORY_SUFFIXES)


def _candidate(element: ElementInfo) -> _Candidate | None:
    templates = element.pad_templates
    if len(templates) != 2 or any(t.presence != "always" for t in templates):
        return None
    sink = next((t for t in templates if t.direction == "sink"), None)
    src = next((t for t in templates if t.direction == "src"), None)
    if sink is None or src is None or not _is_transforming(element):
        return None
    sink_caps, src_caps = concrete_caps(sink.caps), concrete_caps(src.caps)
    if sink_caps.is_any() or src_caps.is_any() or sink_caps.is_empty() or src_caps.is_empty():
        return None
    return _Candidate(element, sink_caps, src_caps, media_names(sink_caps), media_names(src_caps))


class BridgeFinder:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self._candidates = [c for e in catalog.elements if (c := _candidate(e)) is not None]

    def _cost(self, chain: tuple[_Candidate, ...], hardware_ok: bool) -> float:
        cost = 0.0
        for candidate in chain:
            element = candidate.element
            cost += 10 - PREFERRED.get(element.name, 0)
            cost += next((c for rank, c in _RANK_COST if element.rank >= rank), 3)
            if "hardware" in element.categories and not hardware_ok:
                cost += 4
            if element.family == "libav" and element.name not in PREFERRED:
                cost += 1
        return cost

    def find(self, src: Gst.Caps, sink: Gst.Caps, limit: int = 4) -> list[list[str]]:
        """Chains of factory names that can sit between ``src`` and ``sink``."""
        if src.is_any() or sink.is_any() or src.is_empty() or sink.is_empty():
            return []
        src_types, sink_types = media_names(src), media_names(sink)
        first = [c for c in self._candidates if c.sink_types & src_types and c.sink.can_intersect(src)]
        last = [c for c in self._candidates if c.src_types & sink_types and c.src.can_intersect(sink)]
        last_ids = {id(c) for c in last}
        chains: list[tuple[_Candidate, ...]] = [(c,) for c in first if id(c) in last_ids]
        if not chains:
            chains = [(a, b) for a in first for b in last if _chainable(a, b)]
        hardware_ok = has_special_memory(src) or has_special_memory(sink)
        chains.sort(key=lambda chain: (len(chain), self._cost(chain, hardware_ok)))
        return _distinct([[c.element.name for c in chain] for chain in chains], limit)

    def find_parsers(self, src: Gst.Caps, sink: Gst.Caps) -> list[str]:
        """Parsers able to sit between ``src`` and ``sink``, best first."""
        parsers = [
            c
            for c in self._candidates
            if "parser" in c.element.categories and c.sink.can_intersect(src) and c.src.can_intersect(sink)
        ]
        parsers.sort(key=lambda c: self._cost((c,), hardware_ok=False))
        return [c.element.name for c in parsers]


def _chainable(a: _Candidate, b: _Candidate) -> bool:
    """Two-hop chains must not round-trip (encode then decode, pay then depay)."""
    if a is b or not (a.src_types & b.sink_types):
        return False
    roles = set(a.element.categories), set(b.element.categories)
    if "encoder" in roles[0] and "decoder" in roles[1]:
        return False
    if "payloader" in roles[0] and "depayloader" in roles[1]:
        return False
    return a.src.can_intersect(b.sink)


def _distinct(chains: list[list[str]], limit: int) -> list[list[str]]:
    """Keep the best chain per leading element so suggestions are varied."""
    result: list[list[str]] = []
    seen: set[str] = set()
    for chain in chains:
        if chain[0] in seen:
            continue
        seen.add(chain[0])
        result.append(chain)
        if len(result) == limit:
            break
    return result
