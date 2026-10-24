// Performance of a running pipeline: element latency, queue levels and the streaming threads that
// push each link, plus the bottlenecks they reveal.

import type { ElementLatency, QueueLevel, ThreadUsage } from "../api/events";
import type { Graph } from "../api/types";

export interface NodePerf {
  latency?: ElementLatency;
  queue?: QueueLevel;
}

export interface ThreadInfo extends ThreadUsage {
  color: string;
  /** Index in the thread list (stable while the threads do not change). */
  index: number;
}

const THREAD_COLORS = ["#4f9dff", "#3fcf8e", "#f5a524", "#e5484d", "#b07cff", "#2ec4c4", "#ff7ab6", "#a3d14b"];

export function nodePerf(
  graph: Graph,
  elements: Record<string, ElementLatency> = {},
  queues: Record<string, QueueLevel> = {},
): Record<string, NodePerf> {
  const result: Record<string, NodePerf> = {};
  for (const node of graph.nodes) {
    if (elements[node.id] || queues[node.id]) result[node.id] = { latency: elements[node.id], queue: queues[node.id] };
  }
  return result;
}

export function threadsInfo(threads: ThreadUsage[] = []): ThreadInfo[] {
  return threads.map((thread, index) => ({ ...thread, index, color: THREAD_COLORS[index % THREAD_COLORS.length] }));
}

/** Thread pushing each link. */
export function threadOfEdge(threads: ThreadInfo[]): Record<string, ThreadInfo> {
  const result: Record<string, ThreadInfo> = {};
  for (const thread of threads) for (const edge of thread.edges) result[edge] = thread;
  return result;
}

/** Elements a thread runs: the sources and targets of the links it pushes, upstream first. */
export function threadNodes(graph: Graph, thread: ThreadUsage): string[] {
  const nodes: string[] = [];
  for (const edge of graph.edges.filter((e) => thread.edges.includes(e.id))) {
    for (const id of [edge.source, edge.target]) if (!nodes.includes(id)) nodes.push(id);
  }
  return nodes;
}

/** "<element>:<pad>" where the thread starts (the kernel cuts thread names at 15 characters). */
export function threadLabel(graph: Graph, thread: ThreadUsage): string {
  const origin = threadNodes(graph, thread)[0];
  const edge = graph.edges.find((e) => thread.edges.includes(e.id) && e.source === origin);
  const node = graph.nodes.find((n) => n.id === origin);
  return node && edge ? `${node.name}:${edge.source_pad}` : thread.name;
}

export function formatMs(ms: number): string {
  if (ms >= 100) return `${Math.round(ms)} ms`;
  if (ms >= 10) return `${ms.toFixed(1)} ms`;
  return `${ms.toFixed(2)} ms`;
}

export function fillLevel(queue: QueueLevel): "ok" | "warning" | "error" {
  if (queue.fill >= 0.95) return "error";
  return queue.fill >= 0.7 ? "warning" : "ok";
}

const BUSY_CPU = 90;

export interface PerfInsight {
  level: "warning" | "error";
  nodeId: string | null;
  text: string;
}

/** What the numbers suggest: a full queue means what follows it is too slow; a saturated thread needs splitting. */
export function perfInsights(graph: Graph, queues: Record<string, QueueLevel>, threads: ThreadInfo[]): PerfInsight[] {
  const name = (id: string) => graph.nodes.find((node) => node.id === id)?.name ?? id;
  const insights: PerfInsight[] = [];
  for (const [id, queue] of Object.entries(queues)) {
    if (fillLevel(queue) === "ok") continue;
    const drops = queue.overruns ? ` and overflowed ${queue.overruns} times (dropping data if leaky, blocking upstream otherwise)` : "";
    insights.push({
      level: fillLevel(queue) === "error" ? "error" : "warning",
      nodeId: id,
      text: `${name(id)} is ${Math.round(queue.fill * 100)}% full${drops}: the branch after it does not keep up.`,
    });
  }
  for (const thread of threads) {
    if ((thread.cpu ?? 0) < BUSY_CPU) continue;
    const nodes = threadNodes(graph, thread).map(name);
    insights.push({
      level: "warning",
      nodeId: threadNodes(graph, thread)[0] ?? null,
      text: `Thread ${threadLabel(graph, thread)} uses ${Math.round(thread.cpu ?? 0)}% of a core running ${nodes.join(" → ")}: ` +
        "a queue in the middle splits it in two threads.",
    });
  }
  return insights;
}
