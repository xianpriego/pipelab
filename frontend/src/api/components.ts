// Components (macro blocks): library definitions, starters and component files.

import type { Graph } from "./types";

/** JSON primitive: a parameter value. */
export type Value = string | number | boolean | null;

export interface ComponentPort {
  name: string;
  direction: "src" | "sink";
  node_id: string;
  pad: string;
}

export interface ParamTarget {
  node_id: string;
  property: string;
  pad?: string | null;
}

export interface ComponentParam {
  name: string;
  description: string;
  default: Value;
  targets: ParamTarget[];
}

export interface ComponentDef {
  id: string;
  name: string;
  description: string;
  version: number;
  updated_at?: string | null;
  graph: Graph;
  ports: ComponentPort[];
  parameters: ComponentParam[];
}

/** A ready-made component that can be installed into the library. */
export interface StarterInfo {
  id: string;
  name: string;
  description: string;
  available: boolean;
  /** Elements not installed on this machine (e.g. NVIDIA ones without a GPU). */
  missing: string[];
}

/** A component file: the component and the ones it contains, nested first. */
export interface ComponentBundle {
  format: "pipelab-components";
  version: number;
  components: ComponentDef[];
}

export interface ComponentUsage {
  components: { id: string; name: string }[];
  projects: { id: string; name: string }[];
}

export interface GroupResult {
  component: ComponentDef;
  graph: Graph;
}
