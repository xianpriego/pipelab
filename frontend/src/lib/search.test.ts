import { describe, expect, it } from "vitest";
import { summary } from "../test/fixtures";
import { matchScore, searchElements } from "./search";

const elements = [
  summary("x264enc", { rank: 256, long_name: "x264 H.264 Encoder", klass: "Codec/Encoder/Video", categories: ["encoder", "video"], family: "ugly" }),
  summary("nvh264enc", { rank: 257, long_name: "NVENC H.264 Encoder", klass: "Codec/Encoder/Video/Hardware", categories: ["encoder", "hardware", "video"], family: "bad" }),
  summary("h264parse", { rank: 257, long_name: "H.264 parser", klass: "Codec/Parser/Converter/Video", categories: ["parser", "video"], family: "bad" }),
  summary("videoconvert", { long_name: "Colorspace converter", klass: "Filter/Converter/Video", categories: ["converter", "video"] }),
  summary("audioconvert", { rank: 256, long_name: "Audio converter", klass: "Filter/Converter/Audio", categories: ["converter", "audio"] }),
  summary("fallbackswitch", { long_name: "Priority-based fallback switcher", family: "rs" }),
];
const search = (query: string, categories: string[] = [], families: ("rs" | "bad")[] = []) =>
  searchElements(elements, { query, categories, families }).map((e) => e.name);

describe("palette search", () => {
  it("ranks exact name before prefix before substring", () => {
    expect(matchScore(elements[2], "h264parse")).toBe(0);
    expect(matchScore(elements[2], "h264")).toBe(1);
    expect(matchScore(elements[0], "264")).toBe(2);
    expect(search("h264")).toEqual(["h264parse", "nvh264enc", "x264enc"]);
  });

  it("ignores separators inside words", () => {
    expect(search("h.264 encoder")).toEqual(["nvh264enc", "x264enc"]);
    expect(search("h264 enc")).toEqual(["nvh264enc", "x264enc"]);
  });

  it("searches long name, klass and description", () => {
    expect(search("colorspace")).toEqual(["videoconvert"]);
    expect(search("fallback switcher")).toEqual(["fallbackswitch"]);
    expect(search("nothing-like-this")).toEqual([]);
  });

  it("sorts ties by rank then name", () => {
    expect(search("convert")).toEqual(["audioconvert", "videoconvert", "h264parse"]);
  });

  it("requires every selected category and any selected family", () => {
    expect(search("", ["encoder", "hardware"])).toEqual(["nvh264enc"]);
    expect(search("", ["video", "converter"])).toEqual(["videoconvert"]);
    expect(search("", [], ["rs"])).toEqual(["fallbackswitch"]);
    expect(search("enc", [], ["bad"])).toEqual(["nvh264enc"]);
  });
});
