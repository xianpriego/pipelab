import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { MonitorPipeline, MonitorProcess } from "../api/types";
import { Icon } from "../components/Icon";
import { ThemeToggle } from "../components/ThemeToggle";
import { MonitorFlow } from "../monitor/MonitorFlow";
import { notify } from "../store/uiStore";

export function MonitorPage() {
  const [processes, setProcesses] = useState<MonitorProcess[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [pipeline, setPipeline] = useState<MonitorPipeline | null>(null);
  const [loading, setLoading] = useState(false);

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

  const inspect = useCallback(async (process: MonitorProcess) => {
    setSelected(process.pid);
    setLoading(true);
    setPipeline(null);
    try {
      setPipeline(await api.monitorSnapshot(process.pid, "auto"));
    } catch (error) {
      notify({ level: "error", title: `Could not read pid ${process.pid}`, message: errorMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

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
                    className={`monitor-proc${selected === process.pid ? " selected" : ""}`}
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
                  {pipeline.nodes.length} elements · via {pipeline.source.method} ·{" "}
                  {new Date(pipeline.source.captured_at).toLocaleTimeString()}
                </span>
              </div>
              <div className="monitor-flow">
                <MonitorFlow pipeline={pipeline} />
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
