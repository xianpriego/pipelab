"""Component files: a component with the components it contains, to share between machines."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from pipelab.components.models import Component, used_components
from pipelab.components.overlay import dependency_order
from pipelab.graph.models import Graph

FORMAT = "pipelab-components"


class Bundle(BaseModel):
    format: Literal["pipelab-components"] = FORMAT
    version: int = 1
    components: list[Component]  # nested components first


def bundle_of(component: Component, library: dict[str, Component]) -> Bundle:
    needed = used_components(Graph(nodes=component.graph.nodes), library)
    needed[component.id] = component
    return Bundle(components=dependency_order(needed))


def conflicts(bundle: Bundle, library: dict[str, Component]) -> list[str]:
    """Ids of the bundle already in the library."""
    return [component.id for component in bundle.components if component.id in library]
