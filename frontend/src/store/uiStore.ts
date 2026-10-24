// Editor UI state: selection, dock, dialogs, theme and toasts.

import { create } from "zustand";

export type DockTab = "issues" | "bus" | "log" | "preview" | "outputs" | "stats" | "perf" | "probe";
export type Theme = "dark" | "light";
export type ToastLevel = "info" | "success" | "warning" | "error";
export type DialogName = "export" | "import" | "runtime-graph" | null;

export interface ToastAction {
  label: string;
  run: () => void;
}

export interface Toast {
  id: number;
  level: ToastLevel;
  title: string;
  message?: string;
  details?: string[];
  actions?: ToastAction[];
  timeout?: number;
}

interface UiStore {
  selectedNodes: string[];
  selectedEdges: string[];
  dockTab: DockTab;
  dockOpen: boolean;
  dockHeight: number;
  dialog: DialogName;
  theme: Theme;
  toasts: Toast[];
  focusNode: string | null;
  /** Incremented to ask the canvas to fit the whole graph in view. */
  fitRequest: number;
  /** Dots travelling along links while the pipeline runs. */
  flowAnimation: boolean;
  /** Link under the pointer (its toolbar stays a moment after leaving). */
  hoveredEdge: string | null;
  /** While running, links take the colour of the streaming thread that pushes them. */
  threadOverlay: boolean;
  select: (nodes: string[], edges: string[]) => void;
  setDockTab: (tab: DockTab) => void;
  toggleDock: (open?: boolean) => void;
  setDockHeight: (height: number) => void;
  openDialog: (dialog: DialogName) => void;
  setTheme: (theme: Theme) => void;
  notify: (toast: Omit<Toast, "id">) => number;
  dismiss: (id: number) => void;
  requestFocus: (nodeId: string | null) => void;
  requestFit: () => void;
  setFlowAnimation: (enabled: boolean) => void;
  hoverEdge: (edgeId: string | null) => void;
  setThreadOverlay: (enabled: boolean) => void;
}

const THEME_KEY = "pipelab.theme";
const FLOW_KEY = "pipelab.flowAnimation";
const HOVER_GRACE_MS = 350;

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function store(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage unavailable: the choice only lasts for this session.
  }
}

let hoverTimer: ReturnType<typeof setTimeout> | undefined;

let toastSeq = 0;

export const useUiStore = create<UiStore>((set) => ({
  selectedNodes: [],
  selectedEdges: [],
  dockTab: "issues",
  dockOpen: true,
  dockHeight: 240,
  dialog: null,
  theme: stored(THEME_KEY) === "light" ? "light" : "dark",
  toasts: [],
  focusNode: null,
  fitRequest: 0,
  flowAnimation: stored(FLOW_KEY) !== "off",
  hoveredEdge: null,
  threadOverlay: false,
  setThreadOverlay: (threadOverlay) => set({ threadOverlay }),
  select: (nodes, edges) => set({ selectedNodes: nodes, selectedEdges: edges }),
  setDockTab: (tab) => set({ dockTab: tab, dockOpen: true }),
  toggleDock: (open) => set((state) => ({ dockOpen: open ?? !state.dockOpen })),
  setDockHeight: (height) => set({ dockHeight: Math.max(120, Math.min(height, 700)) }),
  openDialog: (dialog) => set({ dialog }),
  setTheme: (theme) => {
    store(THEME_KEY, theme);
    set({ theme });
  },
  setFlowAnimation: (flowAnimation) => {
    store(FLOW_KEY, flowAnimation ? "on" : "off");
    set({ flowAnimation });
  },
  hoverEdge: (edgeId) => {
    clearTimeout(hoverTimer);
    if (edgeId) set({ hoveredEdge: edgeId });
    else hoverTimer = setTimeout(() => set({ hoveredEdge: null }), HOVER_GRACE_MS);
  },
  notify: (toast) => {
    toastSeq += 1;
    const id = toastSeq;
    set((state) => ({ toasts: [...state.toasts.slice(-5), { ...toast, id }] }));
    return id;
  },
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== id) })),
  requestFocus: (nodeId) => set({ focusNode: nodeId }),
  requestFit: () => set((state) => ({ fitRequest: state.fitRequest + 1 })),
}));

export const notify = (toast: Omit<Toast, "id">) => useUiStore.getState().notify(toast);
