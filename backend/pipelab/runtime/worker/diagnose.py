"""Pinpoints which link and which caps field broke a negotiation.

``not-negotiated`` errors are posted by the element that owns the streaming
thread (often the source), far from the culprit. After such an error every
established link is checked: the caps pushed on its source pad against what
its peer can accept, field by field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pipelab.gst import Gst
from pipelab.gst.caps import describe_caps, media_types


@dataclass(frozen=True)
class NegotiationFailure:
    edge_id: str
    text: str


def _field_value(caps: Gst.Caps, media: str, field: str) -> str | None:
    """Textual value of ``field`` in the first structure named ``media``."""
    for index in range(caps.get_size()):
        structure = caps.get_structure(index)
        if structure.get_name() != media or not structure.has_field(field):
            continue
        pattern = rf"(?:^|, ){re.escape(field)}=\([^)]*\)(\[[^\]]*\]|\{{[^}}]*\}}|[^,;]+)"
        match = re.search(pattern, structure.to_string())
        return match.group(1).strip() if match else None
    return None


def _only_field(caps: Gst.Caps, field: str) -> Gst.Caps:
    structure = caps.get_structure(0).copy()
    for index in reversed(range(structure.n_fields())):
        name = structure.nth_field_name(index)
        if name != field:
            structure.remove_field(name)
    features = caps.get_features(0)
    result = Gst.Caps.new_empty()
    result.append_structure_full(structure, features.copy() if features else None)
    return result


def mismatch(caps: Gst.Caps, accepted: Gst.Caps) -> str:
    """Human description of why ``caps`` is not a subset of ``accepted``."""
    media = caps.get_structure(0).get_name()
    if not _only_field(caps, "").can_intersect(accepted):
        return f"{', '.join(media_types(caps))} is not accepted (accepts {describe_caps(accepted)})"
    structure = caps.get_structure(0)
    reasons = []
    for index in range(structure.n_fields()):
        field = structure.nth_field_name(index)
        if not _only_field(caps, field).can_intersect(accepted):
            value = _field_value(caps, media, field)
            allowed = _field_value(accepted, media, field)
            reasons.append(
                f"{field}={value} not in {allowed}" if allowed else f"{field}={value} not accepted"
            )
    return "; ".join(reasons) or "the caps are not accepted"


def find_negotiation_failure(
    edge_pads: dict[str, Gst.Pad], names: dict[str, tuple[str, str]]
) -> NegotiationFailure | None:
    """First link whose negotiated caps its peer refuses. ``names``: edge → (src, dst)."""
    for edge_id, pad in edge_pads.items():
        caps, peer = pad.get_current_caps(), pad.get_peer()
        if caps is None or peer is None or caps.is_empty():
            continue
        accepted = peer.query_caps(None)
        if caps.can_intersect(accepted):
            continue
        source, target = names.get(edge_id, ("?", "?"))
        text = f"{source} → {target}: {mismatch(caps, accepted)}."
        return NegotiationFailure(edge_id=edge_id, text=text)
    return None
