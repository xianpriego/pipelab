"""Pydantic models describing the GStreamer element catalog."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PropertyValue = str | int | float | bool

PropertyType = Literal[
    "boolean",
    "int",
    "uint",
    "int64",
    "uint64",
    "float",
    "double",
    "string",
    "enum",
    "flags",
    "caps",
    "fraction",
    "structure",
    "pad",
    "object",
    "boxed",
    "array",
    "other",
]
Mutability = Literal["null", "ready", "paused", "playing", "unknown"]
Family = Literal["core", "base", "good", "bad", "ugly", "libav", "rs", "other", "component"]
PadDirection = Literal["src", "sink"]
PadPresence = Literal["always", "sometimes", "request"]


class EnumValue(BaseModel):
    value: int
    nick: str
    name: str


class PropertyInfo(BaseModel):
    name: str
    nick: str = ""
    blurb: str = ""
    type: PropertyType
    value_type: str
    default: PropertyValue | None = None
    minimum: float | int | None = None
    maximum: float | int | None = None
    enum_values: list[EnumValue] = Field(default_factory=list)
    readable: bool = True
    writable: bool = True
    construct_only: bool = False
    mutable: Mutability = "unknown"
    controllable: bool = False


class PadSummary(BaseModel):
    name: str
    direction: PadDirection
    presence: PadPresence
    media_types: list[str] = Field(default_factory=list)


class PadTemplateInfo(PadSummary):
    caps: str = "ANY"
    properties: list[PropertyInfo] = Field(default_factory=list)

    def property(self, name: str) -> PropertyInfo | None:
        return next((p for p in self.properties if p.name == name), None)


class ElementSummary(BaseModel):
    name: str
    long_name: str = ""
    klass: str = ""
    description: str = ""
    rank: int = 0
    plugin: str = ""
    family: Family = "other"
    categories: list[str] = Field(default_factory=list)
    pads: list[PadSummary] = Field(default_factory=list)
    preview: Literal["video", "audio"] | None = None
    selectors: list[str] = Field(default_factory=list)


class ElementInfo(ElementSummary):
    author: str = ""
    package: str = ""
    origin: str = ""
    source: str = ""
    hierarchy: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    uri_protocols: list[str] = Field(default_factory=list)
    uri_type: Literal["src", "sink"] | None = None
    pad_templates: list[PadTemplateInfo] = Field(default_factory=list)
    properties: list[PropertyInfo] = Field(default_factory=list)
    introspected: bool = True

    def summary(self) -> ElementSummary:
        return ElementSummary.model_validate(self.model_dump(include=set(ElementSummary.model_fields)))

    def property(self, name: str) -> PropertyInfo | None:
        return next((p for p in self.properties if p.name == name), None)

    def is_a(self, type_name: str) -> bool:
        return type_name in self.hierarchy


class CatalogData(BaseModel):
    gstreamer_version: str
    registry_hash: str
    elements: list[ElementInfo]
    skipped: list[str] = Field(default_factory=list)
