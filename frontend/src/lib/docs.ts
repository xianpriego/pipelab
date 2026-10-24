// Links to the official GStreamer documentation of an element.

import type { ElementSummary } from "../api/types";

const DOCS = "https://gstreamer.freedesktop.org/documentation";

/** Plugins with a single element document it on the plugin index page. */
export function elementDocsUrl(element: ElementSummary, catalog: ElementSummary[]): string {
  const siblings = catalog.filter((other) => other.plugin === element.plugin).length;
  const page = siblings <= 1 ? "index" : element.name;
  return `${DOCS}/${encodeURIComponent(element.plugin)}/${encodeURIComponent(page)}.html?gi-language=c`;
}
