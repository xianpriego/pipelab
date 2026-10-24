"""Builds a graph from a ``gst-launch-1.0`` description."""

from __future__ import annotations

from pipelab.catalog.models import PropertyInfo, PropertyValue
from pipelab.catalog.store import Catalog
from pipelab.graph.editing import default_name
from pipelab.graph.layout import auto_layout
from pipelab.graph.models import Edge, Graph, Node
from pipelab.gst.values import FALSE_WORDS, TRUE_WORDS, parse_bool, parse_number
from pipelab.importer.models import ImportResult
from pipelab.importer.pads import PadResolver
from pipelab.importer.parser import CapsItem, Description, ElementItem, RefItem, parse
from pipelab.importer.tokenizer import tokenize

_INTEGER_TYPES = {"int", "uint", "int64", "uint64"}


def typed_value(info: PropertyInfo | None, raw: str) -> PropertyValue:
    """Convert a textual value to the JSON primitive matching the property type."""
    if info is None:
        return raw
    if info.type == "boolean" and raw.lower() in TRUE_WORDS | FALSE_WORDS:
        return parse_bool(raw)
    if info.type in _INTEGER_TYPES or info.type in ("float", "double"):
        number = parse_number(raw, integer=info.type in _INTEGER_TYPES)
        return raw if number is None else number
    return raw


class _Importer:
    def __init__(self, description: Description, catalog: Catalog) -> None:
        self.description = description
        self.catalog = catalog
        self.graph = Graph()
        self.node_of_item: dict[int, str] = {}

    def warn(self, message: str) -> None:
        self.description.warn(message)

    def _properties(
        self, factory: str, raw: dict[str, str], infos: list[PropertyInfo]
    ) -> dict[str, PropertyValue]:
        by_name = {info.name: info for info in infos}
        known = self.catalog.get(factory) is not None
        values: dict[str, PropertyValue] = {}
        for name, value in raw.items():
            if known and name not in by_name:
                self.warn(f"'{factory}' has no property '{name}'.")
            values[name] = typed_value(by_name.get(name), value)
        return values

    def _node(self, index: int, item: ElementItem | CapsItem) -> Node:
        if isinstance(item, CapsItem):
            return Node(id=f"n{index}", factory="capsfilter", name="", properties={"caps": item.caps})
        element = self.catalog.get(item.factory)
        if element is None:
            self.warn(f"Element '{item.factory}' is not installed.")
        properties = self._properties(item.factory, item.properties, element.properties if element else [])
        pad_properties = {}
        for pad, raw in item.pad_properties.items():
            template = self.catalog.pad_template(item.factory, pad)
            pad_properties[pad] = self._properties(item.factory, raw, template.properties if template else [])
        return Node(
            id=f"n{index}",
            factory=item.factory,
            name=item.name or "",
            properties=properties,
            pad_properties=pad_properties,
        )

    def _assign_names(self) -> None:
        taken: set[str] = set()
        for node in self.graph.nodes:
            if node.name and node.name in taken:
                self.warn(f"Duplicated element name '{node.name}' was renamed.")
                node.name = ""
            taken.add(node.name)
        for node in self.graph.nodes:
            if not node.name:
                node.name = default_name(node.factory, taken)
                taken.add(node.name)

    def create_nodes(self) -> None:
        for index, item in enumerate(self.description.items):
            if isinstance(item, ElementItem | CapsItem):
                node = self._node(len(self.graph.nodes) + 1, item)
                self.graph.nodes.append(node)
                self.node_of_item[index] = node.id
        self._assign_names()

    def _endpoint(self, index: int) -> tuple[str, str | None] | None:
        item = self.description.items[index]
        if isinstance(item, RefItem):
            node = self.graph.node_by_name(item.name)
            if node is None:
                self.warn(f"Reference '{item.name}.' does not match any element.")
                return None
            return node.id, item.pad
        if index in self.node_of_item:
            return self.node_of_item[index], None
        return None

    def create_edges(self) -> None:
        links = []
        for source_index, target_index in self.description.links:
            source, target = self._endpoint(source_index), self._endpoint(target_index)
            if source is not None and target is not None:
                links.append((source, target))
        resolver = PadResolver(self.catalog, self.graph, [(s[0], t[0]) for s, t in links])
        for (source_id, source_pad), (target_id, target_pad) in links:
            pads = resolver.resolve(source_id, source_pad, target_id, target_pad)
            if pads is None:
                names = (self.graph.node(source_id).name, self.graph.node(target_id).name)
                self.warn(f"Could not find compatible pads to link {names[0]} and {names[1]}.")
                continue
            edge_id = f"e{len(self.graph.edges) + 1}"
            self.graph.edges.append(
                Edge(id=edge_id, source=source_id, source_pad=pads[0], target=target_id, target_pad=pads[1])
            )


def import_gst_launch(description: str, catalog: Catalog) -> ImportResult:
    """Parse a gst-launch description into a laid out graph plus warnings."""
    parsed = parse(tokenize(description))
    importer = _Importer(parsed, catalog)
    importer.create_nodes()
    importer.create_edges()
    if not importer.graph.nodes:
        parsed.warn("The description does not contain any element.")
    return ImportResult(graph=auto_layout(importer.graph), warnings=parsed.warnings)
