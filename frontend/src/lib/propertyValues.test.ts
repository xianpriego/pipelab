import { describe, expect, it } from "vitest";
import { prop } from "../test/fixtures";
import {
  formatPropertyValue, isLiveEditable, joinFlags, parsePropertyInput, sliderRange, splitFlags,
} from "./propertyValues";

describe("property values", () => {
  it("parses booleans from checkboxes and text", () => {
    const p = prop("is-live", { type: "boolean" });
    expect(parsePropertyInput(p, true)).toEqual({ ok: true, value: true });
    expect(parsePropertyInput(p, "false")).toEqual({ ok: true, value: false });
    expect(parsePropertyInput(p, "maybe").ok).toBe(false);
  });

  it("validates integers and ranges", () => {
    const p = prop("bitrate", { type: "uint", minimum: 1, maximum: 100 });
    expect(parsePropertyInput(p, "42")).toEqual({ ok: true, value: 42 });
    expect(parsePropertyInput(p, "4.5")).toEqual({ ok: false, error: "Must be an integer" });
    expect(parsePropertyInput(p, "0")).toEqual({ ok: false, error: "Minimum is 1" });
    expect(parsePropertyInput(p, "101")).toEqual({ ok: false, error: "Maximum is 100" });
    expect(parsePropertyInput(p, "abc").ok).toBe(false);
  });

  it("accepts floats for double properties", () => {
    expect(parsePropertyInput(prop("volume", { type: "double", minimum: 0, maximum: 10 }), "0.5"))
      .toEqual({ ok: true, value: 0.5 });
  });

  it("maps enum input to the nick", () => {
    const p = prop("pattern", {
      type: "enum",
      enum_values: [{ value: 0, nick: "smpte", name: "SMPTE 100% color bars" }, { value: 18, nick: "ball", name: "Moving ball" }],
    });
    expect(parsePropertyInput(p, "ball")).toEqual({ ok: true, value: "ball" });
    expect(parsePropertyInput(p, "18")).toEqual({ ok: true, value: "ball" });
    expect(parsePropertyInput(p, "Moving ball")).toEqual({ ok: true, value: "ball" });
    expect(parsePropertyInput(p, "square").ok).toBe(false);
  });

  it("validates fractions", () => {
    const p = prop("framerate", { type: "fraction" });
    expect(parsePropertyInput(p, " 30 / 1 ")).toEqual({ ok: true, value: "30/1" });
    expect(parsePropertyInput(p, "30").ok).toBe(false);
  });

  it("keeps caps and strings verbatim", () => {
    expect(parsePropertyInput(prop("caps", { type: "caps" }), "video/x-raw,width=640")).toEqual({
      ok: true, value: "video/x-raw,width=640",
    });
  });

  it("splits and joins flags", () => {
    expect(splitFlags("a+b")).toEqual(["a", "b"]);
    expect(splitFlags("0")).toEqual([]);
    expect(joinFlags([])).toBe("0");
    expect(joinFlags(["x", "y"])).toBe("x+y");
  });

  it("formats values for inputs", () => {
    expect(formatPropertyValue(true)).toBe("true");
    expect(formatPropertyValue(undefined)).toBe("");
    expect(formatPropertyValue(3)).toBe("3");
  });

  it("knows what can change while playing", () => {
    expect(isLiveEditable(prop("a", { mutable: "playing" }))).toBe(true);
    expect(isLiveEditable(prop("b", { controllable: true }))).toBe(true);
    expect(isLiveEditable(prop("active-pad", { type: "pad" }))).toBe(true);
    expect(isLiveEditable(prop("c", { mutable: "ready" }))).toBe(false);
    expect(isLiveEditable(prop("d", { mutable: "playing", construct_only: true }))).toBe(false);
    expect(isLiveEditable(prop("e", { mutable: "playing", writable: false }))).toBe(false);
  });

  it("offers sliders only for bounded, reasonable ranges", () => {
    expect(sliderRange(prop("alpha", { type: "double", minimum: 0, maximum: 1 }))).toEqual([0, 1]);
    expect(sliderRange(prop("big", { type: "uint64", minimum: 0, maximum: 1.8e19 }))).toBeNull();
    expect(sliderRange(prop("s", { type: "string" }))).toBeNull();
  });
});
