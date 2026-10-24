"""Ready-made probe scripts offered in the UI (sources live in ``recipes/``)."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

_SOURCES = Path(__file__).parent / "recipes"


class Recipe(BaseModel):
    id: str
    name: str
    description: str
    target_kind: Literal["node", "edge"]
    factories: list[str] = Field(default_factory=list)
    code: str


_RECIPES = [
    (
        "keyframe-switch",
        "Switch on keyframe",
        "node",
        ["input-selector", "output-selector"],
        "Selecting another pad waits for the next keyframe (and requests one upstream).",
    ),
    (
        "drop-until-keyframe",
        "Drop until keyframe",
        "edge",
        [],
        "Drops delta frames until the first key unit; waits again after a flush.",
    ),
    (
        "gate",
        "Gate (open/close)",
        "edge",
        [],
        "Trigger opens or closes the link; reopening waits for a keyframe.",
    ),
    (
        "packet-loss",
        "Simulate packet loss",
        "edge",
        [],
        "Drops a percentage of buffers, in bursts; change it live with Trigger.",
    ),
    (
        "periodic-keyframe",
        "Request keyframes",
        "edge",
        [],
        "Asks the encoder upstream for a key unit every N seconds or on Trigger.",
    ),
    (
        "stall-detector",
        "Stall detector",
        "edge",
        [],
        "Warns when no buffer crosses the link for a while, and when it flows again.",
    ),
    (
        "eos-after",
        "EOS after N seconds",
        "edge",
        [],
        "Sends EOS downstream after a fixed duration (finalises recordings).",
    ),
    ("log-events", "Log events", "edge", [], "Logs caps, segments, tags, EOS and flushes crossing the link."),
    ("custom-link", "Custom link probe", "edge", [], "A documented starting point for your own probe."),
    (
        "custom-element",
        "Custom element script",
        "node",
        [],
        "A documented starting point for a script on an element (properties, triggers, pads).",
    ),
]


@cache
def recipes() -> list[Recipe]:
    return [
        Recipe(
            id=recipe_id,
            name=name,
            description=description,
            target_kind=kind,
            factories=factories,
            code=(_SOURCES / f"{recipe_id.replace('-', '_')}.py").read_text(),
        )
        for recipe_id, name, kind, factories, description in _RECIPES
    ]
