import { describe, expect, it } from "vitest";
import type { ElementSummary } from "../api/types";
import { elementDocsUrl } from "./docs";

const element = (name: string, plugin: string) => ({ name, plugin }) as ElementSummary;

describe("elementDocsUrl", () => {
  it("links multi-element plugins to the element page", () => {
    const catalog = [element("queue", "coreelements"), element("tee", "coreelements")];
    expect(elementDocsUrl(catalog[0], catalog)).toBe(
      "https://gstreamer.freedesktop.org/documentation/coreelements/queue.html?gi-language=c",
    );
  });

  it("links single-element plugins to the plugin index", () => {
    const catalog = [element("x264enc", "x264")];
    expect(elementDocsUrl(catalog[0], catalog)).toBe(
      "https://gstreamer.freedesktop.org/documentation/x264/index.html?gi-language=c",
    );
  });
});
