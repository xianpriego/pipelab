"""Exposes library components as virtual catalog elements (``component:<id>``).

With them in the catalog, validation, link checks, layout, the palette and the
caps flow treat component instances exactly like elements.
"""

from __future__ import annotations

from pipelab.catalog.classify import media_types
from pipelab.catalog.models import ElementInfo, PadSummary, PadTemplateInfo, PropertyInfo
from pipelab.catalog.store import Catalog
from pipelab.components.models import Component, ComponentParam, ComponentPort, component_id
from pipelab.graph.caps_flow import CapsFlow, caps_to_string


def dependency_order(components: dict[str, Component]) -> list[Component]:
    """Components ordered so that nested ones come first; cyclic ones are left out."""
    ordered: list[Component] = []
    state: dict[str, str] = {}

    def visit(component: Component) -> bool:
        if state.get(component.id) == "done":
            return True
        if state.get(component.id) == "visiting":
            return False
        state[component.id] = "visiting"
        for node in component.graph.nodes:
            inner = component_id(node.factory)
            if inner and inner in components and not visit(components[inner]):
                return False
        state[component.id] = "done"
        ordered.append(component)
        return True

    for component in components.values():
        visit(component)
    return ordered


def _port_template(component: Component, port: ComponentPort, catalog: Catalog) -> PadTemplateInfo:
    node = component.graph.node(port.node_id)
    inner = catalog.pad_template(node.factory, port.pad) if node else None
    flow = CapsFlow(component.graph, catalog)
    if node is None:
        caps = "ANY"
    elif port.direction == "src":
        caps = caps_to_string(flow.output_caps(node.id, port.pad))
    else:
        caps = caps_to_string(flow.input_caps(node.id, port.pad))
    presence = "sometimes" if inner is not None and inner.presence == "sometimes" else "always"
    return PadTemplateInfo(
        name=port.name, direction=port.direction, presence=presence, caps=caps, media_types=media_types(caps)
    )


def _param_property(component: Component, param: ComponentParam, catalog: Catalog) -> PropertyInfo:
    source: PropertyInfo | None = None
    for target in param.targets:
        node = component.graph.node(target.node_id)
        if node is None:
            continue
        if target.pad:
            template = catalog.pad_template(node.factory, target.pad)
            source = (
                next((p for p in template.properties if p.name == target.property), None)
                if template
                else None
            )
        else:
            element = catalog.get(node.factory)
            source = element.property(target.property) if element else None
        if source is not None:
            break
    if source is None:
        return PropertyInfo(
            name=param.name,
            blurb=param.description,
            type="string",
            value_type="gchararray",
            default=param.default,
        )
    return source.model_copy(
        update={
            "name": param.name,
            "nick": param.name,
            "blurb": param.description or source.blurb,
            "default": param.default if param.default is not None else source.default,
            "construct_only": False,
        }
    )


def component_element(component: Component, catalog: Catalog) -> ElementInfo:
    templates = [_port_template(component, port, catalog) for port in component.ports]
    directions = {t.direction for t in templates}
    media = {m.split("/")[0] for t in templates for m in t.media_types if "/" in m}
    categories = {"component"} | {m for m in media if m in ("video", "audio", "text")}
    if "sink" not in directions:
        categories.add("source")
    if "src" not in directions:
        categories.add("sink")
    return ElementInfo(
        name=component.factory,
        long_name=component.name,
        klass="Component",
        description=component.description or f"Component with {len(component.graph.nodes)} elements",
        family="component",
        plugin="components",
        categories=sorted(categories),
        pads=[
            PadSummary.model_validate(t.model_dump(include=set(PadSummary.model_fields))) for t in templates
        ],
        pad_templates=templates,
        properties=[_param_property(component, p, catalog) for p in component.parameters],
        hierarchy=["GstBin", "GstElement"],
    )


def overlay_catalog(base: Catalog, components: dict[str, Component]) -> Catalog:
    """``base`` plus one virtual element per (non cyclic) component."""
    catalog = base
    for component in dependency_order(components):
        catalog = catalog.extended([component_element(component, catalog)])
    return catalog
