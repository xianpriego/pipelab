import type { ElementSummary, GraphNode, PadSummary, PropertyInfo } from "../api/types";

export function pad(name: string, direction: "src" | "sink", presence: PadSummary["presence"], media = ["ANY"]): PadSummary {
  return { name, direction, presence, media_types: media };
}

export function summary(name: string, patch: Partial<ElementSummary> = {}): ElementSummary {
  return {
    name, long_name: `${name} long`, klass: "Generic", description: `${name} description`, rank: 0,
    plugin: "test", family: "base", categories: [], pads: [], ...patch,
  };
}

export function node(id: string, factory: string, patch: Partial<GraphNode> = {}): GraphNode {
  return {
    id, factory, name: id, properties: {}, pad_properties: {}, position: { x: 0, y: 0 }, preview: "auto", ...patch,
  };
}

export function prop(name: string, patch: Partial<PropertyInfo> = {}): PropertyInfo {
  return {
    name, nick: name, blurb: `${name} blurb`, type: "string", value_type: "gchararray", default: null,
    minimum: null, maximum: null, enum_values: [], readable: true, writable: true, construct_only: false,
    mutable: "unknown", controllable: false, ...patch,
  };
}
