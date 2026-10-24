import { describe, expect, it } from "vitest";
import { mediaClass, packetPlan } from "./packets";

describe("packet plan", () => {
  it("draws nothing for idle links", () => {
    expect(packetPlan(0, 0).count).toBe(0);
    expect(packetPlan(Number.NaN, 0).count).toBe(0);
  });

  it("grows density logarithmically with the buffer rate and caps it", () => {
    const counts = [1, 5, 30, 100, 5000].map((fps) => packetPlan(fps, 1e6).count);
    expect(counts).toEqual([1, 2, 4, 5, 6]);
    expect([...counts].sort((a, b) => a - b)).toEqual(counts);
  });

  it("sizes dots by bitrate within a small range", () => {
    const small = packetPlan(30, 64_000).radius;
    const large = packetPlan(30, 50_000_000).radius;
    expect(small).toBeGreaterThanOrEqual(2);
    expect(large).toBeLessThanOrEqual(4.5);
    expect(large).toBeGreaterThan(small);
  });
});

describe("media class", () => {
  it("classifies negotiated caps", () => {
    expect(mediaClass("video/x-raw, format=(string)I420")).toBe("video");
    expect(mediaClass("video/x-raw(memory:CUDAMemory), format=NV12")).toBe("video");
    expect(mediaClass("audio/x-raw, rate=(int)48000")).toBe("audio");
    expect(mediaClass("video/x-h264, stream-format=(string)avc")).toBe("encoded");
    expect(mediaClass("application/x-rtp, media=(string)video")).toBe("encoded");
    expect(mediaClass("text/x-raw")).toBe("other");
    expect(mediaClass(undefined)).toBe("other");
  });
});
