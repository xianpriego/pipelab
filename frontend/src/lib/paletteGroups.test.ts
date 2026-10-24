import { beforeEach, describe, expect, it } from "vitest";
import { summary } from "../test/fixtures";
import { groupElements, loadExpanded, primaryGroup, saveExpanded } from "./paletteGroups";

const element = (name: string, categories: string[]) => summary(name, { categories });

describe("palette groups", () => {
  it("assigns each element to one primary group by priority", () => {
    expect(primaryGroup(element("udpsrc", ["network", "source"]))).toBe("sources");
    expect(primaryGroup(element("hlssink2", ["muxer", "sink"]))).toBe("sinks");
    expect(primaryGroup(element("splitmuxsink", ["bin", "generic", "muxer"]))).toBe("muxers");
    expect(primaryGroup(element("h264parse", ["converter", "parser", "video"]))).toBe("parsers");
    expect(primaryGroup(element("nvh264enc", ["encoder", "hardware", "video"]))).toBe("encoders");
    expect(primaryGroup(element("rtph264pay", ["network", "payloader"]))).toBe("rtp");
    expect(primaryGroup(element("input-selector", ["generic"]))).toBe("mixers");
    expect(primaryGroup(element("audiomixer", ["audio", "generic"]))).toBe("mixers");
    expect(primaryGroup(element("compositor", ["filter", "mixer", "video"]))).toBe("mixers");
    expect(primaryGroup(element("videoconvert", ["converter", "filter", "video"]))).toBe("converters");
    expect(primaryGroup(element("rtpjitterbuffer", ["filter", "network"]))).toBe("network");
    expect(primaryGroup(element("videobalance", ["effect", "filter", "video"]))).toBe("effects");
    expect(primaryGroup(element("queue", ["generic"]))).toBe("plumbing");
    expect(primaryGroup(element("mystery", []))).toBe("other");
  });

  it("returns non-empty groups in display order with counts", () => {
    const groups = groupElements([
      element("queue", ["generic"]), element("fakesink", ["sink"]), element("videotestsrc", ["source"]),
      element("audiotestsrc", ["source"]),
    ]);
    expect(groups.map((group) => [group.id, group.elements.length])).toEqual([
      ["sources", 2], ["sinks", 1], ["plumbing", 1],
    ]);
    expect(groups[0].elements.map((e) => e.name)).toEqual(["videotestsrc", "audiotestsrc"]);
  });
});

describe("expanded groups storage", () => {
  beforeEach(() => localStorage.clear());

  it("round-trips and tolerates garbage", () => {
    expect(loadExpanded()).toEqual([]);
    saveExpanded(["sources", "sinks"]);
    expect(loadExpanded()).toEqual(["sources", "sinks"]);
    localStorage.setItem("pipelab.palette.expanded", "{nope");
    expect(loadExpanded()).toEqual([]);
  });
});
