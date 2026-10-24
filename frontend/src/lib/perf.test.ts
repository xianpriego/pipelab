import { describe, expect, it } from "vitest";
import type { QueueLevel } from "../api/events";
import { node } from "../test/fixtures";
import { nodePerf, perfInsights, threadLabel, threadNodes, threadOfEdge, threadsInfo } from "./perf";

const graph = {
  nodes: [node("src", "videotestsrc"), node("q", "queue"), node("enc", "x264enc"), node("sink", "fakesink")],
  edges: [
    { id: "e1", source: "src", source_pad: "src", target: "q", target_pad: "sink" },
    { id: "e2", source: "q", source_pad: "src", target: "enc", target_pad: "sink" },
    { id: "e3", source: "enc", source_pad: "src", target: "sink", target_pad: "sink" },
  ],
};

const level = (fill: number, overruns = 0): QueueLevel => ({
  buffers: 0, bytes: 0, time_ms: 0, max_buffers: 200, max_bytes: 0, max_time_ms: 1000, fill, overruns, underruns: 0,
});

describe("performance data", () => {
  it("attaches latency and queue levels to their nodes", () => {
    const perf = nodePerf(graph, { enc: { avg_ms: 12, max_ms: 20, samples: 30 } }, { q: level(0.5) });
    expect(Object.keys(perf).sort()).toEqual(["enc", "q"]);
    expect(perf.enc.latency?.avg_ms).toBe(12);
    expect(perf.q.queue?.fill).toBe(0.5);
  });

  it("maps links to the thread pushing them and lists what each thread runs", () => {
    const threads = threadsInfo([
      { id: 1, name: "src:src", cpu: 5, edges: ["e1"] },
      { id: 2, name: "q:src", cpu: 97, edges: ["e2", "e3"] },
    ]);
    expect(threadOfEdge(threads).e3.name).toBe("q:src");
    expect(threads[0].color).not.toBe(threads[1].color);
    expect(threadNodes(graph, threads[1])).toEqual(["q", "enc", "sink"]);
    expect(threadLabel(graph, { id: 3, name: "videotestsrc0:s", cpu: 1, edges: ["e1"] })).toBe("src:src");
  });

  it("points at full queues and saturated threads", () => {
    const threads = threadsInfo([{ id: 2, name: "q:src", cpu: 97, edges: ["e2", "e3"] }]);
    const insights = perfInsights(graph, { q: level(1, 12) }, threads);
    expect(insights.map((i) => [i.level, i.nodeId])).toEqual([["error", "q"], ["warning", "q"]]);
    expect(insights[0].text).toContain("overflowed 12 times");
    expect(insights[1].text).toContain("q → enc → sink");
    expect(perfInsights(graph, { q: level(0.2) }, threadsInfo([{ id: 2, name: "x", cpu: 10, edges: [] }]))).toEqual([]);
  });
});
