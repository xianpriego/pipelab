import { useMemo, useState } from "react";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useAutoScroll } from "./useAutoScroll";

const VISIBLE = 1000;
const LEVEL = /\b(ERROR|WARN|FIXME|INFO|DEBUG|LOG|TRACE)\b/;

export function LogPanel() {
  const logs = useRuntimeStore((state) => state.logs);
  const [text, setText] = useState("");
  const [follow, setFollow] = useState(true);
  const visible = useMemo(() => {
    const q = text.trim().toLowerCase();
    const filtered = q ? logs.filter((entry) => entry.line.toLowerCase().includes(q)) : logs;
    return filtered.slice(-VISIBLE);
  }, [logs, text]);
  const scroller = useAutoScroll<HTMLPreElement>(visible.length, follow);

  return (
    <div className="panel-with-toolbar">
      <div className="panel-toolbar">
        <input className="input" placeholder="Filter GST_DEBUG output…" value={text} onChange={(e) => setText(e.target.value)} />
        <label className="row muted nowrap">
          <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> follow
        </label>
        <span className="muted nowrap">{visible.length} / {logs.length} lines</span>
      </div>
      <pre className="log-view" ref={scroller}>
        {visible.length === 0 ? <span className="faint">No log output. Raise GST_DEBUG in the toolbar for more detail.</span> : null}
        {visible.map((entry) => {
          const level = LEVEL.exec(entry.line)?.[1] ?? "";
          return (
            <span key={entry.seq} className={`log-line lvl-${level.toLowerCase()}`}>
              {entry.line}
              {"\n"}
            </span>
          );
        })}
      </pre>
    </div>
  );
}
