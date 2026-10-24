"""Builds graphs into GStreamer containers; component instances become GstBins.

Every graph level is a ``Scope``: the top-level graph in the pipeline, and the
graph of each component instance inside its bin. Ids inside an instance are
prefixed with the instance path (``"<instance id>/<inner id>"``) so runtime
events stay unambiguous; element names are the node names, unique per bin.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipelab.catalog.store import template_regex
from pipelab.components.models import Component, ComponentPort, component_id
from pipelab.graph.models import Edge, Graph, Node
from pipelab.gst import Gst
from pipelab.runtime.worker.builder import BuiltPipeline, apply_property, create_element, is_pad_property
from pipelab.runtime.worker.encoder import PreviewSettings
from pipelab.runtime.worker.links import Linker, get_pad
from pipelab.runtime.worker.previews import preview_kind

OnLinked = Callable[[str, Edge, Gst.Pad], None]  # (global edge id, edge, source pad)


@dataclass
class Scope:
    prefix: str  # "" at top level, "<instance path>/" inside instances
    instance: str  # instance (bin) name, "" at top level
    graph: Graph
    container: Gst.Bin
    elements: dict[str, Gst.Element] = field(default_factory=dict)  # local node id → element

    def element_named(self, name: str) -> Gst.Element | None:
        node = self.graph.node_by_name(name)
        return self.elements.get(node.id) if node else None

    def global_id(self, local_id: str) -> str:
        return f"{self.prefix}{local_id}"


class Assembler:
    def __init__(
        self,
        components: dict[str, Component],
        preview: PreviewSettings,
        emit: Callable[..., None],
        built: BuiltPipeline,
        on_linked: OnLinked,
    ) -> None:
        self._components = components
        self._preview = preview
        self._emit = emit
        self._built = built
        self._on_linked = on_linked

    def build_scope(self, graph: Graph, container: Gst.Bin, prefix: str = "", instance: str = "") -> Scope:
        scope = Scope(prefix, instance, graph, container)
        self._built.scopes.append(scope)
        for node in graph.nodes:
            element = self._create(node, scope)
            if element is None:
                continue
            container.add(element)
            scope.elements[node.id] = element
            self._register(scope, node, element)
        if self._built.errors:
            return scope
        linker = Linker(
            graph,
            scope.elements,
            self._emit,
            lambda edge, pad: self._on_linked(scope.global_id(edge.id), edge, pad),
            prefix=prefix,
        )
        self._built.errors += [(None, text) for text in linker.link_all()]
        self._apply_pad_typed(scope)
        return scope

    def _register(self, scope: Scope, node: Node, element: Gst.Element) -> None:
        global_id = scope.global_id(node.id)
        self._built.elements[global_id] = element
        self._built.element_ids[element] = global_id

    def _create(self, node: Node, scope: Scope) -> Gst.Element | None:
        definition = component_id(node.factory)
        if definition is not None:
            component = self._components.get(definition)
            if component is None:
                self._built.errors.append((node, f"Component '{definition}' is not in the library"))
                return None
            return self.build_instance(node.name, component, node.properties, scope.global_id(node.id) + "/")
        element = create_element(node, self._preview, self._emit, self._built)
        if element is None:
            self._built.errors.append(
                (node, f"Element '{node.factory}' could not be created (missing plugin?)")
            )
            return None
        if preview_kind(node) is None:
            for name, value in node.properties.items():
                if not is_pad_property(element, name) and (error := apply_property(element, name, value)):
                    self._built.errors.append((node, f"{node.name}: {error}"))
        return element

    def build_instance(self, name: str, component: Component, params: dict[str, Any], prefix: str) -> Gst.Bin:
        """A GstBin running ``component`` with ``params``; one ghost pad per port."""
        container = Gst.Bin.new(name)
        scope = self.build_scope(component.graph, container, prefix, instance=name)
        self._apply_parameters(scope, component, params)
        for port in component.ports:
            self._expose(container, scope, port)
        return container

    def _apply_parameters(self, scope: Scope, component: Component, params: dict[str, Any]) -> None:
        for param in component.parameters:
            value = params.get(param.name, param.default)
            if value is None:
                continue
            for target in param.targets:
                element = scope.elements.get(target.node_id)
                owner = get_pad(element, target.pad) if element is not None and target.pad else element
                if owner is not None and (error := apply_property(owner, target.property, value)):
                    self._built.errors.append((None, f"{scope.instance}.{param.name}: {error}"))

    def _expose(self, container: Gst.Bin, scope: Scope, port: ComponentPort) -> None:
        element = scope.elements.get(port.node_id)
        if element is None:
            return
        pad = get_pad(element, port.pad)
        if pad is not None:
            container.add_pad(Gst.GhostPad.new(port.name, pad))
            return

        def on_pad_added(_element: Gst.Element, new_pad: Gst.Pad) -> None:  # sometimes pad → late ghost
            template = new_pad.get_pad_template()
            name = template.name_template if template else new_pad.get_name()
            matches = port.pad in (new_pad.get_name(), name) or template_regex(port.pad).match(
                new_pad.get_name()
            )
            if matches and container.get_static_pad(port.name) is None:
                ghost = Gst.GhostPad.new(port.name, new_pad)
                ghost.set_active(True)
                container.add_pad(ghost)

        element.connect("pad-added", on_pad_added)

    def _apply_pad_typed(self, scope: Scope) -> None:
        """GstPad-typed properties (input-selector active-pad) need linked pads."""
        for node in scope.graph.nodes:
            element = scope.elements.get(node.id)
            if element is None or preview_kind(node) is not None or component_id(node.factory):
                continue
            for name, value in node.properties.items():
                if is_pad_property(element, name) and (error := apply_property(element, name, value)):
                    self._built.errors.append((node, f"{node.name}: {error}"))
