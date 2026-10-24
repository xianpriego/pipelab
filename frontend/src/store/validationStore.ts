// Validation issues of the current graph, indexed by node and edge.

import { create } from "zustand";
import type { Issue, Severity } from "../api/types";

const ORDER: Record<Severity, number> = { info: 1, warning: 2, error: 3 };

export function worstSeverity(a: Severity | undefined, b: Severity): Severity {
  return a && ORDER[a] >= ORDER[b] ? a : b;
}

export interface IssueCounts {
  error: number;
  warning: number;
  info: number;
}

interface ValidationStore {
  issues: Issue[];
  byNode: Record<string, Severity>;
  byEdge: Record<string, Severity>;
  counts: IssueCounts;
  pending: boolean;
  error: string | null;
  setIssues: (issues: Issue[]) => void;
  setPending: (pending: boolean) => void;
  setError: (error: string | null) => void;
}

export function indexIssues(issues: Issue[]) {
  const byNode: Record<string, Severity> = {};
  const byEdge: Record<string, Severity> = {};
  const counts: IssueCounts = { error: 0, warning: 0, info: 0 };
  for (const issue of issues) {
    counts[issue.severity] += 1;
    for (const id of issue.node_ids) byNode[id] = worstSeverity(byNode[id], issue.severity);
    for (const id of issue.edge_ids) byEdge[id] = worstSeverity(byEdge[id], issue.severity);
  }
  return { byNode, byEdge, counts };
}

export const useValidationStore = create<ValidationStore>((set) => ({
  issues: [],
  byNode: {},
  byEdge: {},
  counts: { error: 0, warning: 0, info: 0 },
  pending: false,
  error: null,
  setIssues: (issues) => set({ issues, ...indexIssues(issues), pending: false, error: null }),
  setPending: (pending) => set({ pending }),
  setError: (error) => set({ error, pending: false }),
}));
