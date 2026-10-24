"""In-memory catalog with fast lookups used by validation, export and import."""

from __future__ import annotations

import re
from functools import lru_cache

from pipelab.catalog.classify import inferred_any_caps
from pipelab.catalog.models import CatalogData, ElementInfo, ElementSummary, PadTemplateInfo
from pipelab.gst import Gst
from pipelab.gst.caps import parse_caps

_PAD_PATTERN = {"%u": r"\d+", "%d": r"-?\d+", "%s": r".+"}


@lru_cache(maxsize=512)
def template_regex(template_name: str) -> re.Pattern[str]:
    pattern = re.escape(template_name)
    for token, regex in _PAD_PATTERN.items():
        pattern = pattern.replace(re.escape(token), regex)
    return re.compile(f"^{pattern}$")


def is_template_name(pad_name: str) -> bool:
    return any(token in pad_name for token in _PAD_PATTERN)


class Catalog:
    def __init__(self, data: CatalogData) -> None:
        self.data = data
        self._elements = {element.name: element for element in data.elements}
        self._summaries = [element.summary() for element in data.elements]

    def extended(self, extra: list[ElementInfo]) -> Catalog:
        """A catalog with ``extra`` (virtual) elements, sharing everything else."""
        clone = object.__new__(Catalog)
        clone.data = self.data.model_copy(update={"elements": [*self.data.elements, *extra]})
        clone._elements = {**self._elements, **{element.name: element for element in extra}}
        clone._summaries = [*self._summaries, *(element.summary() for element in extra)]
        return clone

    def __contains__(self, name: str) -> bool:
        return name in self._elements

    def __len__(self) -> int:
        return len(self._elements)

    @property
    def elements(self) -> list[ElementInfo]:
        return self.data.elements

    def get(self, name: str) -> ElementInfo | None:
        return self._elements.get(name)

    def summaries(self) -> list[ElementSummary]:
        return self._summaries

    def pad_template(self, factory: str, pad_name: str) -> PadTemplateInfo | None:
        """Template a concrete (``sink_3``) or template (``sink_%u``) pad belongs to."""
        element = self.get(factory)
        if element is None:
            return None
        for template in element.pad_templates:
            if template.name == pad_name:
                return template
        for template in element.pad_templates:
            if template.presence != "always" and template_regex(template.name).match(pad_name):
                return template
        return None

    def templates(self, factory: str, direction: str) -> list[PadTemplateInfo]:
        element = self.get(factory)
        if element is None:
            return []
        return [t for t in element.pad_templates if t.direction == direction]

    def template_caps(self, factory: str, pad_name: str) -> Gst.Caps:
        """Template caps of a pad, with ANY narrowed for audio/video sinks and sources."""
        template = self.pad_template(factory, pad_name)
        if template is None:
            return Gst.Caps.new_any()
        if template.caps == "ANY":
            element = self._elements[factory]
            inferred = inferred_any_caps(element.klass, template.direction)
            if inferred is not None:
                return parse_caps(inferred)
        return parse_caps(template.caps)
