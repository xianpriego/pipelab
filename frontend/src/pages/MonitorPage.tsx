import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { MonitorPipeline, MonitorProcess, MonitorStats } from "../api/types";
import { Icon } from "../components/Icon";
import { ThemeToggle } from "../components/ThemeToggle";
import { formatMs } from "../lib/perf";
import { MonitorFlow } from "../monitor/MonitorFlow";
import { notify } from "../store/uiStore";

const STATS_INTERVAL = 1000;
const STRUCTURE_INTERVAL = 5000;

export function MonitorPage() {
  const [processes, setProcesses] = useState<MonitorProcess[] | null>(null);
  const [selected, setSelected] = useState<MonitorProcess | null>(null);
  const [pipeline, setPipeline] = useState<MonitorPipeline | null>(null);
  const [stats, setStats] = useState<MonitorStats | null>(null);
  const [loading, setLoading] = useState(false);
  const timers = useRef<number[]>([]);

  const refresh = useCallback(async () => {
    try {
      setProcesses(await api.monitorProcesses());
    } catch (error) {
      setProcesses([]);
      notify({ level: "error", title: "Could not list processes", message: errorMessage(error) });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((id) => window.clearInterval(id));
    timers.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const inspect = useCallback(
    async (process: MonitorProcess) => {
      clearTimers();
      setSelected(process);
      setLoading(true);
      setPipeline(null);
      setStats(null);
      try {
        const snapshot = await api.monitorSnapshot(process.pid, "auto");
        setPipeline(snapshot);
        setLoading(false);

        // Keep the structure fresh (elements appearing/leaving, state changes).
        timers.current.push(
          window.setInterval(() => {
            api.monitorSnapshot(process.pid, "auto").then(setPipeline).catch(() => undefined);
          }, STRUCTURE_INTERVAL),
        );
        // Live statistics, if the process was launched with the GStreamer tracers.
        if (process.full_stats) {
          const poll = () => api.monitorLive(process.pid).then(setStats).catch(() => undefined);
          void poll();
          timers.current.push(window.setInterval(poll, STATS_INTERVAL));
        }
      } catch (error) {
        setLoading(false);
        notify({ level: "error", title: `Could not read pid ${process.pid}`, message: errorMessage(error) });
      }
    },
    [clearTimers],
  );

  const live = selected?.full_stats && stats?.available;

  return (
    <div className="monitor-page">
      <header className="monitor-topbar">
        <Link to="/" className="monitor-back" title="Back to pipelines">
          <Icon name="back" size={16} /> Pipelines
        </Link>
        <h1>Live monitor</h1>
        <div className="monitor-topbar-spacer" />
        <button className="btn" onClick={() => void refresh()}>
          <Icon name="refresh" size={15} /> Rescan
        </button>
        <ThemeToggle />
      </header>

      <div className="monitor-body">
        <aside className="monitor-sidebar">
          <p className="monitor-hint">
            GStreamer processes on this machine. Pick one to reconstruct its pipeline, read-only.
          </p>
          {processes === null ? (
            <div className="monitor-empty"><span className="spinner" /></div>
          ) : processes.length === 0 ? (
            <div className="monitor-empty">
              <p>No GStreamer processes found.</p>
              <p className="monitor-dim">
                Only processes visible to the API are listed. To see others, run the API with the
                host PID namespace (see the monitor docs).
              </p>
            </div>
          ) : (
            <ul className="monitor-proc-list">
              {processes.map((process) => (
                <li key={process.pid}>
                  <button
                    className={`monitor-proc${selected?.pid === process.pid ? " selected" : ""}`}
                    onClick={() => void inspect(process)}
                  >
                    <div className="monitor-proc-head">
                      <span className="monitor-proc-name">{process.process || "gstreamer"}</span>
                      <span className="monitor-proc-pid">pid {process.pid}</span>
                    </div>
                    <div className="monitor-proc-cmd" title={process.cmdline}>{process.cmdline}</div>
                    <div className="monitor-proc-tags">
                      {process.is_pipelab ? <span className="tag tag-self">pipelab</span> : null}
                      {process.container ? (
                        <span className="tag tag-container" title={`container ${process.container}`}>
                          {process.container.slice(0, 12)}
                        </span>
                      ) : null}
                      {process.full_stats ? (
                        <span className="tag tag-live" title="Launched with GStreamer tracers: full live stats">
                          live stats
                        </span>
                      ) : null}
                      {process.methods.map((method) => (
                        <span key={method} className="tag tag-method">{method}</span>
                      ))}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="monitor-canvas">
          {loading ? (
            <div className="monitor-empty"><span className="spinner" /> Reading pipeline…</div>
          ) : pipeline ? (
            <>
              <div className="monitor-meta">
                <strong>{pipeline.name}</strong>
                <span className="monitor-dim">
                  {pipeline.nodes.length} elements · via {pipeline.source.method}
                </span>
                {live ? (
                  <span className="monitor-live-pill"><span className="monitor-live-dot" /> live</span>
                ) : null}
                {live && stats?.end_to_end ? (
                  <span className="monitor-dim">end-to-end latency {formatMs(stats.end_to_end.avg_ms)}</span>
                ) : null}
              </div>
              {selected && !selected.full_stats ? (
                <div className="monitor-notice">
                  <Icon name="info" size={15} />
                  <span>
                    Structure, element states and caps only. For live throughput, latencies and
                    threads, launch this pipeline with{" "}
                    <code>GST_TRACERS="stats;latency(flags=pipeline+element)"</code>,{" "}
                    <code>GST_DEBUG=GST_TRACER:7</code> and a readable <code>GST_DEBUG_FILE</code>.
                  </span>
                </div>
              ) : null}
              <div className="monitor-flow">
                <MonitorFlow pipeline={pipeline} stats={live ? stats : null} />
              </div>
            </>
          ) : (
            <div className="monitor-empty monitor-placeholder">
              <Icon name="graph" size={28} />
              <p>Select a process to reconstruct its pipeline.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
