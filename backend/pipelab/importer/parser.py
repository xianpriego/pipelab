"""Turns gst-launch tokens into declared items and the links between them."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pipelab.importer.tokenizer import Token, looks_like_caps

_PROPERTY = re.compile(r"^([A-Za-z_][\w\-]*)(?:::([A-Za-z_][\w\-]*))?=(.*)$", re.DOTALL)
_REFERENCE = re.compile(r"^([\w\-]+)\.([\w%\-]*)$")
_FACTORY = re.compile(r"^[\w\-]+$")
_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")


@dataclass
class ElementItem:
    factory: str
    name: str | None = None
    properties: dict[str, str] = field(default_factory=dict)
    pad_properties: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class CapsItem:
    caps: str


@dataclass(frozen=True)
class RefItem:
    name: str
    pad: str | None


Item = ElementItem | CapsItem | RefItem | None  # None: skipped (unsupported) token


@dataclass
class Description:
    items: list[Item] = field(default_factory=list)
    links: list[tuple[int, int]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)


def _classify(description: Description, token: Token) -> Item:
    text = token.text
    if _URI.match(text):
        description.warn(f"URI '{text}' used as an element is not supported; it was skipped.")
        return None
    if token.quoted or looks_like_caps(text):
        return CapsItem(text.strip())
    reference = _REFERENCE.match(text)
    if reference:
        return RefItem(reference.group(1), reference.group(2) or None)
    if not _FACTORY.match(text):
        description.warn(f"Unrecognised token '{text}' was skipped.")
        return None
    return ElementItem(factory=text)


def _assign(description: Description, element: ElementItem, token: Token) -> bool:
    match = _PROPERTY.match(token.text)
    if token.quoted or match is None:
        return False
    first, second, value = match.groups()
    if second is not None:
        element.pad_properties.setdefault(first, {})[second] = value
    elif first == "name":
        element.name = value
    else:
        element.properties[first] = value
    return True


def parse(tokens: list[Token]) -> Description:
    description = Description()
    previous: int | None = None
    pending_link = False
    element: ElementItem | None = None
    for token in tokens:
        if token.kind == "link":
            if previous is None:
                description.warn("A '!' without an element on its left was ignored.")
            pending_link, element = True, None
            continue
        if token.kind in ("open", "close"):
            description.warn("Bins '( … )' were flattened into the pipeline.")
            continue
        if element is not None and not pending_link and _assign(description, element, token):
            continue
        if _PROPERTY.match(token.text) and not token.quoted and not looks_like_caps(token.text):
            description.warn(f"Property '{token.text}' has no element to apply to; it was ignored.")
            continue
        item = _classify(description, token)
        index = len(description.items)
        description.items.append(item)
        if pending_link and previous is not None:
            description.links.append((previous, index))
        pending_link = False
        previous = index
        element = item if isinstance(item, ElementItem) else None
    if pending_link:
        description.warn("The description ends with a dangling '!'.")
    return description
