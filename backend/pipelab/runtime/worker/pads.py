"""Finding pads by the names used in graphs: pad names or pad template names."""

from __future__ import annotations

from pipelab.catalog.store import template_regex
from pipelab.gst import Gst


def _template(element: Gst.Element, pad_name: str) -> Gst.StaticPadTemplate | None:
    templates = element.get_factory().get_static_pad_templates() if element.get_factory() else []
    for template in templates:
        if template.name_template == pad_name:
            return template
    for template in templates:
        if template.presence != Gst.PadPresence.ALWAYS and template_regex(template.name_template).match(
            pad_name
        ):
            return template
    return None


def get_pad(element: Gst.Element, pad_name: str) -> Gst.Pad | None:
    """Existing pad, or a newly requested one for request templates."""
    pad = element.get_static_pad(pad_name)
    if pad is not None:
        return pad
    template = _template(element, pad_name)
    if template is not None and template.presence == Gst.PadPresence.REQUEST:
        return element.request_pad_simple(pad_name)
    return None


def pad_matches(pad: Gst.Pad, wanted: str) -> bool:
    """Whether a pad that just appeared is the one a graph names ``wanted`` (name or template)."""
    if wanted == pad.get_name():
        return True
    template = pad.get_pad_template()
    if template is not None and template.name_template == wanted:
        return True
    return bool(template_regex(wanted).match(pad.get_name()))
