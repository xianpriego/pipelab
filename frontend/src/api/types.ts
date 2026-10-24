// TypeScript mirror of the backend pydantic models (docs/ARCHITECTURE.md).

export type PropertyValue = string | number | boolean;

export type PropertyType =
  | "boolean" | "int" | "uint" | "int64" | "uint64" | "float" | "double" | "string"
  | "enum" | "flags" | "caps" | "fraction" | "structure" | "pad" | "object" | "boxed"
  | "array" | "other";
export type Mutability = "null" | "ready" | "paused" | "playing" | "unknown";
export type Family = "core" | "base" | "good" | "bad" | "ugly" | "libav" | "rs" | "component" | "other";
export type PadDirection = "src" | "sink";
export type PadPresence = "always" | "sometimes" | "request";

export interface EnumValue {
  value: number;
  nick: string;
  name: string;
}

export interface PropertyInfo {
  name: string;
  nick: string;
  blurb: string;
  type: PropertyType;
  value_type: string;
  default: PropertyValue | null;
  minimum: number | null;
  maximum: number | null;
  enum_values: EnumValue[];
  readable: boolean;
  writable: boolean;
  construct_only: boolean;
  mutable: Mutability;
  controllable: boolean;
}

export interface PadSummary {
  name: string;
  direction: PadDirection;
  presence: PadPresence;
  media_types: string[];
}

export interface PadTemplateInfo extends PadSummary {
  caps: string;
  properties: PropertyInfo[];
}

export interface ElementSummary {
  name: string;
  long_name: string;
  klass: string;
  description: string;
  rank: number;
  plugin: string;
  family: Family;
  categories: string[];
  pads: PadSummary[];
  preview?: "video" | "audio" | null;
  /** Writable GstPad-typed properties (e.g. input-selector "active-pad"). */
  selectors?: string[];
}

export interface ElementInfo extends ElementSummary {
  author: string;
  package: string;
  origin: string;
  source: string;
  hierarchy: string[];
  interfaces: string[];
  uri_protocols: string[];
  uri_type: "src" | "sink" | null;
  pad_templates: PadTemplateInfo[];
  properties: PropertyInfo[];
  introspected: boolean;
}

// --- Graph -----------------------------------------------------------------

export interface Position {
  x: number;
  y: number;
}

export interface GraphNode {
  id: string;
  factory: string;
  name: string;
  properties: Record<string, PropertyValue>;
  pad_properties: Record<string, Record<string, PropertyValue>>;
  position: Position;
  preview: "auto" | "off";
}

export interface GraphEdge {
  id: string;
  source: string;
  source_pad: string;
  target: string;
  target_pad: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type Severity = "error" | "warning" | "info";

export interface FixElement {
  factory: string;
  properties: Record<string, PropertyValue>;
}

export interface PadRef {
  node_id: string;
  pad: string;
}

export type FixKind = "insert_on_edge" | "connect_via" | "set_property" | "insert_tee" | "insert_after";

export interface Fix {
  kind: FixKind;
  edge_id?: string | null;
  edge_ids?: string[];
  node_id?: string | null;
  source?: PadRef | null;
  target?: PadRef | null;
  elements?: FixElement[];
  property?: string | null;
  value?: PropertyValue | null;
}

export interface Suggestion {
  title: string;
  description: string;
  fix: Fix;
}

export interface Issue {
  id: string;
  rule: string;
  severity: Severity;
  message: string;
  node_ids: string[];
  edge_ids: string[];
  suggestions: Suggestion[];
}

export interface LinkCheckResult {
  allowed: boolean;
  severity: "ok" | Severity;
  edge: GraphEdge;
  source_caps: string;
  target_caps: string;
  common_caps: string | null;
  issues: Issue[];
}

// --- Projects ----------------------------------------------------------------

export interface ProjectSettings {
  gst_debug: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  graph: Graph;
  settings: ProjectSettings;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  node_count: number;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  template?: string | null;
  graph?: Graph | null;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  graph?: Graph;
  settings?: ProjectSettings;
}

export interface TemplateInfo {
  id: string;
  name: string;
  description: string;
  available: boolean;
  missing: string[];
}

// --- Health ------------------------------------------------------------------

export type CatalogState = "idle" | "building" | "ready" | "error";

export interface Health {
  status: string;
  gstreamer_version: string;
  catalog: { state: CatalogState; done: number; total: number; count: number; error: string | null };
}

// --- Export / import ---------------------------------------------------------

export interface ExportFormat {
  id: string;
  label: string;
  language: string;
  extension: string;
  description: string;
}

export interface ExportResult {
  format: string;
  filename: string;
  language: string;
  content: string;
}

export interface ImportResult {
  graph: Graph;
  warnings: string[];
}

// --- Runtime -----------------------------------------------------------------

export type RuntimeState =
  | "idle" | "starting" | "ready" | "paused" | "playing" | "stopping" | "stopped" | "error";

export interface RuntimeStatus {
  project_id: string;
  state: RuntimeState;
  started_at: number | null;
  error: string | null;
}

export interface PropertyChange {
  node_id: string;
  property: string;
  value: PropertyValue;
  pad?: string | null;
}

export interface LiveProperties {
  node_id: string;
  properties: Record<string, PropertyValue | null>;
  pads?: Record<string, Record<string, PropertyValue | null>>;
}

export interface PropertyResult {
  ok: boolean;
  value?: PropertyValue | null;
  error?: string | null;
}

export interface TapResult {
  ok: boolean;
  error?: string | null;
}

export type ProbeResult = TapResult;

export interface MediaFile {
  path: string;
  size: number;
  modified: number | string;
  mime: string | null;
}
