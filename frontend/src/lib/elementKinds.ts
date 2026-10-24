// Visual classification of elements (accent colours, preview sinks).

import type { ElementSummary } from "../api/types";

const ACCENTS: [string, string][] = [
  ["component", "var(--accent-component)"],
  ["source", "var(--accent-source)"],
  ["sink", "var(--accent-sink)"],
  ["encoder", "var(--accent-codec)"],
  ["decoder", "var(--accent-codec)"],
  ["parser", "var(--accent-parser)"],
  ["muxer", "var(--accent-mux)"],
  ["demuxer", "var(--accent-mux)"],
  ["payloader", "var(--accent-network)"],
  ["depayloader", "var(--accent-network)"],
  ["mixer", "var(--accent-mixer)"],
  ["converter", "var(--accent-converter)"],
  ["effect", "var(--accent-effect)"],
  ["filter", "var(--accent-effect)"],
];

const MIXER_NAME = /(mixer|selector|funnel|adder)$/;

export function accentColor(summary: ElementSummary | undefined): string {
  if (!summary) return "var(--danger)";
  const match = ACCENTS.find(([category]) => summary.categories.includes(category));
  if (match) return match[1];
  return MIXER_NAME.test(summary.name) ? "var(--accent-mixer)" : "var(--accent-generic)";
}

/** Sinks the runtime replaces by a browser preview (decided by the backend catalog). */
export function previewKind(summary: ElementSummary | undefined): "video" | "audio" | null {
  return summary?.preview ?? null;
}
