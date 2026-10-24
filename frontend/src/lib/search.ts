// Palette search: ranking by name match quality, then rank, with category/family filters.

import type { ElementSummary, Family } from "../api/types";

export interface PaletteFilters {
  query: string;
  categories: string[];
  families: Family[];
}

export const EMPTY_FILTERS: PaletteFilters = { query: "", categories: [], families: [] };

/** Lowercase and drop separators inside words so "H.264" matches "h264". */
export function normalize(text: string): string {
  return text.toLowerCase().replace(/([a-z0-9])[.\-_]+(?=[a-z0-9])/g, "$1");
}

/** Lower is better; null means no match. */
export function matchScore(element: ElementSummary, query: string): number | null {
  const q = normalize(query.trim());
  if (!q) return 0;
  const name = normalize(element.name);
  if (name === q) return 0;
  if (name.startsWith(q)) return 1;
  if (name.includes(q)) return 2;
  const terms = q.split(/\s+/).filter(Boolean);
  const haystacks = [element.long_name, element.klass, element.description].map(normalize);
  for (const [index, text] of haystacks.entries()) {
    if (text.includes(q)) return 3 + index;
  }
  const all = `${name} ${haystacks.join(" ")}`;
  return terms.length > 1 && terms.every((term) => all.includes(term)) ? 6 : null;
}

function matchesFilters(element: ElementSummary, filters: PaletteFilters): boolean {
  if (filters.families.length > 0 && !filters.families.includes(element.family)) return false;
  return filters.categories.every((category) => element.categories.includes(category));
}

export function searchElements(elements: ElementSummary[], filters: PaletteFilters): ElementSummary[] {
  const scored: { element: ElementSummary; score: number }[] = [];
  for (const element of elements) {
    if (!matchesFilters(element, filters)) continue;
    const score = matchScore(element, filters.query);
    if (score !== null) scored.push({ element, score });
  }
  scored.sort(
    (a, b) => a.score - b.score || b.element.rank - a.element.rank || a.element.name.localeCompare(b.element.name),
  );
  return scored.map((entry) => entry.element);
}

export const CATEGORY_FILTERS = [
  "source", "sink", "encoder", "decoder", "parser", "muxer", "demuxer", "converter", "effect",
  "mixer", "payloader", "depayloader", "network", "hardware", "audio", "video",
];

export const FAMILY_FILTERS: Family[] = ["core", "base", "good", "bad", "ugly", "libav", "rs", "other"];

export const COMMON_ELEMENTS = [
  "videotestsrc", "audiotestsrc", "filesrc", "uridecodebin", "v4l2src", "udpsrc", "rtspsrc",
  "queue", "tee", "capsfilter", "videoconvert", "videoscale", "videorate", "audioconvert",
  "audioresample", "x264enc", "nvh264enc", "h264parse", "avdec_h264", "decodebin", "mp4mux",
  "matroskamux", "qtdemux", "rtph264pay", "rtph264depay", "compositor", "audiomixer",
  "input-selector", "autovideosink", "autoaudiosink", "fakesink", "filesink", "udpsink",
];
