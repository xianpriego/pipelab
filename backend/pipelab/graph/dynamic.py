"""Dynamic pipelines: slots of component instances and pipeline API functions.

Semantics are specified in docs/DYNAMIC.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pipelab.graph.probes import Action, Value

ParamType = Literal["string", "int", "float", "bool"]


class SlotLink(BaseModel):
    """Connects one port of every instance to a pad of the static graph."""

    port: str  # component port name
    node_id: str  # element of the enclosing graph
    pad: str  # usually a request template (compositor sink_%u, tee src_%u)
    pad_properties: dict[str, Value] = Field(default_factory=dict)  # "$index" = instance index


class SlotInstance(BaseModel):
    id: str  # e.g. "input0"; also the bin name
    params: dict[str, Value] = Field(default_factory=dict)


class CanvasPosition(BaseModel):
    x: float = 0.0
    y: float = 0.0


class Slot(BaseModel):
    id: str
    name: str  # plural, e.g. "inputs" → list_inputs()
    item: str  # singular, e.g. "input" → add_input(), remove_input(), restart_input()
    component: str  # component id in the library
    links: list[SlotLink] = Field(default_factory=list)
    initial: list[SlotInstance] = Field(default_factory=list)  # instances built before PLAYING
    max_instances: int | None = None
    position: CanvasPosition | None = None  # where the editor draws the slot


class FunctionParam(BaseModel):
    name: str
    type: ParamType = "string"
    default: Value = None
    description: str = ""


class ApiFunction(BaseModel):
    """A method the pipeline exposes to the software owning it."""

    name: str  # snake_case identifier
    description: str = ""
    params: list[FunctionParam] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)  # "$<param>" references the arguments
