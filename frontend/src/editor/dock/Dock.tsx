import { useMemo, useRef, type PointerEvent } from "react";
import { Icon } from "../../components/Icon";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useUiStore, type DockTab } from "../../store/uiStore";
import { useValidationStore } from "../../store/validationStore";
import { BusPanel } from "./BusPanel";
import { IssuesPanel } from "./IssuesPanel";
import { LogPanel } from "./LogPanel";
import { OutputsPanel } from "./OutputsPanel";
import { PreviewPanel } from "./PreviewPanel";
import { ProbePanel } from "./ProbePanel";
import { useProbeStore } from "../../store/probeStore";
import { StatsPanel } from "./StatsPanel";
import { PerfPanel } from "./PerfPanel";
import { perfInsights, threadsInfo } from "../../lib/perf";
import { useGraphStore } from "../../store/graphStore";

const TABS: [DockTab, string][] = [
  ["issues", "Issues"],
  ["preview", "Preview"],
  ["bus", "Bus"],
  ["log", "Log"],
  ["stats", "Stats"],
  ["perf", "Performance"],
  ["probe", "Probe"],
  ["outputs", "Outputs"],
];

function useTabBadges(): Partial<Record<DockTab, { count: number; level: string }>> {
  const counts = useValidationStore((state) => state.counts);
  const busErrors = useRuntimeStore((state) => state.bus.filter((event) => event.kind === "error").length);
  const busCount = useRuntimeStore((state) => state.bus.length);
  const probed = useProbeStore((state) => state.probed.length);
  const graph = useGraphStore((state) => state.graph);
  const stats = useRuntimeStore((state) => state.stats);
  const bottlenecks = useMemo(
    () => (stats ? perfInsights(graph, stats.queues ?? {}, threadsInfo(stats.threads)).length : 0),
    [graph, stats],
  );
  const issues = counts.error + counts.warning + counts.info;
  const issueLevel = counts.error ? "error" : counts.warning ? "warning" : "info";
  return {
    issues: issues ? { count: issues, level: issueLevel } : undefined,
    bus: busCount ? { count: busErrors || busCount, level: busErrors ? "error" : "" } : undefined,
    probe: probed ? { count: probed, level: "primary" } : undefined,
    perf: bottlenecks ? { count: bottlenecks, level: "warning" } : undefined,
  };
}

export function Dock() {
  const tab = useUiStore((state) => state.dockTab);
  const open = useUiStore((state) => state.dockOpen);
  const setTab = useUiStore((state) => state.setDockTab);
  const toggle = useUiStore((state) => state.toggleDock);
  const badges = useTabBadges();
  const drag = useRef<{ y: number; height: number } | null>(null);

  const onPointerDown = (event: PointerEvent) => {
    drag.current = { y: event.clientY, height: useUiStore.getState().dockHeight };
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: PointerEvent) => {
    if (!drag.current) return;
    useUiStore.getState().setDockHeight(drag.current.height + drag.current.y - event.clientY);
  };

  return (
    <section className={`dock${open ? "" : " collapsed"}`}>
      {open ? (
        <div className="dock-resizer" onPointerDown={onPointerDown} onPointerMove={onPointerMove}
          onPointerUp={() => (drag.current = null)} />
      ) : null}
      <div className="dock-tabs tabs" role="tablist">
        {TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={open && tab === id}
            className={`tab${open && tab === id ? " active" : ""}`} onClick={() => setTab(id)}>
            {label}
            {badges[id] ? <span className={`badge ${badges[id]?.level}`}>{badges[id]?.count}</span> : null}
          </button>
        ))}
        <span className="spacer" />
        <button className="icon-btn" onClick={() => toggle()} aria-label={open ? "Collapse panel" : "Expand panel"}>
          <Icon name={open ? "chevronDown" : "chevronUp"} />
        </button>
      </div>
      {open ? (
        <div className="dock-body">
          {tab === "issues" ? <IssuesPanel /> : null}
          {tab === "bus" ? <BusPanel /> : null}
          {tab === "log" ? <LogPanel /> : null}
          {tab === "preview" ? <PreviewPanel /> : null}
          {tab === "outputs" ? <OutputsPanel /> : null}
          {tab === "stats" ? <StatsPanel /> : null}
          {tab === "perf" ? <PerfPanel /> : null}
          {tab === "probe" ? <ProbePanel /> : null}
        </div>
      ) : null}
    </section>
  );
}
