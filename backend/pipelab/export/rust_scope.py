"""Rust statements building one graph scope (the pipeline or a component bin)."""

from __future__ import annotations

from pipelab.export.common import PropertySpec
from pipelab.export.plan import ScopePlan
from pipelab.export.rust_syntax import rust_str, typed_literal
from pipelab.graph.models import Graph


def _property_list(specs: tuple[PropertySpec, ...]) -> str:
    return "&[" + ", ".join(f"({rust_str(p.name)}, {rust_str(p.text)})" for p in specs) + "]"


def _format_id(text: str) -> str:
    return rust_str(text.replace("{", "{{").replace("}", "}}"))[1:-1]


class ScopeRenderer:
    """Rust statements building a graph scope into ``container`` / ``elements``."""

    def __init__(self, types: dict[int, str], host: str) -> None:
        self.types = types
        self.host = host  # expression of the &ProbeHost

    def elements(self, scope: ScopePlan, nested: dict[str, list[str]] | None = None) -> list[str]:
        lines = []
        for element in scope.spec.elements:
            key = rust_str(element.name)
            instance = scope.instances.get(element.node.id)
            if instance is None:
                make = f"rt::make_element(&container, {rust_str(element.factory)}, {key}, "
                lines.append(f"elements.insert({key}.into(), {make}{_property_list(element.properties)})?);")
                continue
            component = instance.component
            fields = []
            for param in component.params:
                literal = typed_literal(param.kind, instance.values.get(param.name))
                if param.name in instance.values and literal is not None:
                    fields.append(f"{param.ident}: Some({literal})")
            overrides = (nested or {}).get(element.name, [])
            binding = f"let {'mut ' if overrides else ''}args_{element.ident}"
            if fields:
                rest = ", ..Default::default()" if len(fields) < len(component.params) else ""
                lines.append(f"{binding} = {component.type_name}Params {{ {', '.join(fields)}{rest} }};")
            else:
                lines.append(f"{binding} = {component.type_name}Params::default();")
            lines += overrides
            build = f"build_{component.ident}({key}, &args_{element.ident}, {self.host})?"
            lines += [
                f"let bin_{element.ident} = {build};",
                f"container.add(&bin_{element.ident})?;",
                f"elements.insert({key}.into(), bin_{element.ident}.upcast());",
            ]
        return lines

    def links(self, scope: ScopePlan) -> list[str]:
        lines = []
        for link in scope.spec.links:
            function = "link_dynamic" if link.edge.id in scope.dynamic_edges else "link"
            args = ", ".join(
                rust_str(a) for a in (link.source.name, link.source_pad, link.target.name, link.target_pad)
            )
            lines.append(f"rt::{function}(&elements, {args})?;")
        for element in scope.spec.elements:
            if element.node.id in scope.instances:
                continue
            target = f"&elements[{rust_str(element.name)}]"
            for pad, specs in element.pad_properties:
                lines.append(f"rt::configure_pad({target}, {rust_str(pad)}, {_property_list(specs)})?;")
            for ref in element.pad_refs:
                value = f"Value::from({rust_str(ref.text)})"
                lines.append(f"rt::apply_value({target}, {rust_str(ref.name)}, &{value}, None)?;")
        return lines

    def probes(self, scope: ScopePlan, graph: Graph, in_component: bool) -> list[str]:
        lines = []
        for rule_set in scope.probes:
            target = rule_set.target
            if target.kind == "edge":
                edge = graph.edge(target.id)
                node, pad = (graph.node(edge.source), edge.source_pad) if edge else (None, None)
            else:
                node, pad = graph.node(target.id), target.pad
            if node is None:
                continue
            probe_id = (
                f'format!("{{name}}/{_format_id(rule_set.id)}")'
                if in_component
                else f"{rust_str(rule_set.id)}.to_string()"
            )
            pad_arg = f"Some({rust_str(pad)})" if pad else "None"
            instance = "name" if in_component else '""'
            lines.append(
                f"rt::RuleSet::attach({self.host}, &elements, {rust_str(node.name)}, {pad_arg}, {probe_id}, "
                f"{instance}, {rust_str(node.name)}, {self.types[id(rule_set)]}::new())?;"
            )
        return lines
