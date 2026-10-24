// Palette groups: every element goes to exactly one functional group.

import type { ElementSummary } from "../api/types";

export type GroupId =
  | "components" | "sources" | "sinks" | "decoders" | "encoders" | "parsers" | "demuxers" | "muxers" | "rtp"
  | "converters" | "effects" | "mixers" | "network" | "plumbing" | "other";

export interface PaletteGroup {
  id: GroupId;
  label: string;
  elements: ElementSummary[];
}

/** Display order of the groups. */
export const GROUP_LABELS: [GroupId, string][] = [
  ["components", "Components"],
  ["sources", "Sources"],
  ["sinks", "Sinks"],
  ["decoders", "Decoders"],
  ["encoders", "Encoders"],
  ["parsers", "Parsers"],
  ["demuxers", "Demuxers"],
  ["muxers", "Muxers"],
  ["rtp", "RTP payloaders"],
  ["converters", "Converters & scalers"],
  ["effects", "Effects & filters"],
  ["mixers", "Mixers & selectors"],
  ["network", "Network"],
  ["plumbing", "Plumbing (queues, tees, caps…)"],
  ["other", "Other"],
];

/** Colour of each group, following the element accents (green sources → blue processing → red sinks). */
export const GROUP_ACCENTS: Record<GroupId, string> = {
  components: "var(--accent-component)", sources: "var(--accent-source)", sinks: "var(--accent-sink)", decoders: "var(--accent-codec)",
  encoders: "var(--accent-codec)", parsers: "var(--accent-parser)", demuxers: "var(--accent-mux)",
  muxers: "var(--accent-mux)", rtp: "var(--accent-network)", converters: "var(--accent-converter)",
  effects: "var(--accent-effect)", mixers: "var(--accent-mixer)", network: "var(--accent-network)",
  plumbing: "var(--accent-generic)", other: "var(--accent-generic)",
};

const MIXER_NAME = /(mixer|selector|funnel|adder|switch|synchronizer|^concat)$/;
const has = (element: ElementSummary, ...categories: string[]) =>
  categories.some((category) => element.categories.includes(category));

/** Assignment priority: the first matching rule wins (a sink muxer is a sink). */
const RULES: [GroupId, (element: ElementSummary) => boolean][] = [
  ["components", (e) => e.family === "component" || has(e, "component")],
  ["sources", (e) => has(e, "source")],
  ["sinks", (e) => has(e, "sink")],
  ["demuxers", (e) => has(e, "demuxer")],
  ["muxers", (e) => has(e, "muxer")],
  ["decoders", (e) => has(e, "decoder")],
  ["encoders", (e) => has(e, "encoder")],
  ["parsers", (e) => has(e, "parser")],
  ["rtp", (e) => has(e, "payloader", "depayloader")],
  ["mixers", (e) => has(e, "mixer") || MIXER_NAME.test(e.name)],
  ["converters", (e) => has(e, "converter")],
  ["network", (e) => has(e, "network")],
  ["effects", (e) => has(e, "effect", "filter", "analyzer")],
  ["plumbing", (e) => has(e, "generic")],
];

export function primaryGroup(element: ElementSummary): GroupId {
  return RULES.find(([, matches]) => matches(element))?.[0] ?? "other";
}

/** Non-empty groups in display order, keeping the order of ``elements`` inside each. */
export function groupElements(elements: ElementSummary[]): PaletteGroup[] {
  const buckets = new Map<GroupId, ElementSummary[]>();
  for (const element of elements) {
    const id = primaryGroup(element);
    const bucket = buckets.get(id);
    if (bucket) bucket.push(element);
    else buckets.set(id, [element]);
  }
  return GROUP_LABELS
    .filter(([id]) => buckets.has(id))
    .map(([id, label]) => ({ id, label, elements: buckets.get(id) ?? [] }));
}

const STORAGE_KEY = "pipelab.palette.expanded";

export function loadExpanded(): GroupId[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(value) ? value.filter((item): item is GroupId => typeof item === "string") : [];
  } catch {
    return [];
  }
}

export function saveExpanded(groups: GroupId[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(groups));
  } catch {
    // Storage unavailable: the layout only lasts for this session.
  }
}
