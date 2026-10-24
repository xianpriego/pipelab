// Components, probe rules, slots and pipeline API functions (docs/DYNAMIC.md).

import type { Graph } from "./types";

/** JSON primitive; strings starting with "$" reference a variable/builtin/argument ("$$" escapes). */
export type Value = string | number | boolean | null;

export type TriggerType = "start" | "buffer" | "event" | "idle" | "resumed" | "interval" | "property" | "signal";
export type ConditionType =
  | "keyframe" | "flag" | "size" | "pts-gap" | "pts-backwards" | "every" | "rate" | "caps-field" | "variable"
  | "pad" | "random";
export type ActionType =
  | "pass" | "drop" | "block" | "unblock" | "remove-probe" | "post-message" | "set-property" | "send-event"
  | "request-keyframe" | "set-variable" | "increment" | "log" | "signal" | "call" | "add-instance"
  | "remove-instance" | "restart-instance";
export type Operator = "==" | "!=" | "<" | "<=" | ">" | ">=";

export interface Trigger {
  type: TriggerType;
  event?: string | null;
  ms?: number | null;
  property?: string | null;
  name?: string | null;
}

export interface Condition {
  type: ConditionType;
  negate?: boolean;
  flag?: string | null;
  op?: Operator | null;
  value?: Value;
  field?: string | null;
  name?: string | null;
  n?: number | null;
  percent?: number | null;
}

export interface Action {
  type: ActionType;
  node?: string | null;
  pad?: Value;
  property?: string | null;
  value?: Value;
  name?: string | null;
  fields?: Record<string, Value>;
  message?: string | null;
  level?: "info" | "warning" | "error";
  event?: string | null;
  direction?: "downstream" | "upstream";
  by?: number;
  probe?: string | null;
  function?: string | null;
  args?: Record<string, Value>;
  slot?: string | null;
  params?: Record<string, Value>;
  instance?: Value;
}

export interface ProbeRule {
  id: string;
  when: Trigger;
  conditions: Condition[];
  actions: Action[];
}

export interface ProbeTarget {
  kind: "node" | "edge";
  id: string;
  /** Node targets: a pad name or template; null = all sink pads. */
  pad?: string | null;
}

export interface ProbeRuleSet {
  id: string;
  name: string;
  enabled: boolean;
  target: ProbeTarget;
  variables: Record<string, Value>;
  rules: ProbeRule[];
}

export interface SlotLink {
  port: string;
  node_id: string;
  pad: string;
  /** Values may use "$index" (instance number) and "$id". */
  pad_properties: Record<string, Value>;
}

export interface SlotInstance {
  id: string;
  params: Record<string, Value>;
}

export interface Slot {
  id: string;
  /** Plural: list_<name>(). */
  name: string;
  /** Singular: add_<item>(), remove_<item>(), restart_<item>(). */
  item: string;
  component: string;
  links: SlotLink[];
  initial: SlotInstance[];
  max_instances?: number | null;
  position?: { x: number; y: number } | null;
}

export type ParamType = "string" | "int" | "float" | "bool";

export interface FunctionParam {
  name: string;
  type: ParamType;
  default?: Value;
  description?: string;
}

export interface ApiFunction {
  name: string;
  description: string;
  params: FunctionParam[];
  actions: Action[];
}

// --- Components ----------------------------------------------------------------

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

// --- Probe rule schema (GET /api/probes/schema) ----------------------------------

export type FieldKind =
  | "int" | "ms" | "float" | "percent" | "string" | "value" | "op" | "event" | "flag" | "node" | "pad"
  | "property" | "function" | "slot" | "fields" | "args" | "params" | "level" | "direction" | "probe" | "bool"
  | "instance";

export interface FieldSpec {
  name: string;
  kind: FieldKind;
  label: string;
  required?: boolean;
  options?: string[] | null;
}

export interface Spec {
  type: string;
  label: string;
  description: string;
  fields: FieldSpec[];
}

export interface ProbeSchema {
  triggers: Spec[];
  conditions: Spec[];
  actions: Spec[];
  builtins: { name: string; description: string }[];
  events: string[];
  flags: string[];
  operators: string[];
}

// --- Runtime ----------------------------------------------------------------------

export interface CallResult {
  ok: boolean;
  result?: unknown;
  error?: string | null;
}

export interface InstancesResult {
  slots: Record<string, SlotInstance[]>;
}
