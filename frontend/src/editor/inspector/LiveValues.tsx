import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { LiveProperties, PropertyValue } from "../../api/types";
import { useProjectStore } from "../../store/projectStore";
import { notify } from "../../store/uiStore";

export function LiveValues({ nodeId }: { nodeId: string }) {
  const projectId = useProjectStore((state) => state.meta?.id);
  const [values, setValues] = useState<LiveProperties | null>(null);
  const [auto, setAuto] = useState(false);

  const read = useCallback(async () => {
    if (!projectId) return;
    try {
      const result = await api.runtimeProperties(projectId, nodeId);
      setValues(result);
    } catch (err) {
      setAuto(false);
      notify({ level: "error", title: "Cannot read live values", message: errorMessage(err) });
    }
  }, [projectId, nodeId]);

  useEffect(() => {
    if (!auto) return undefined;
    void read();
    const timer = setInterval(() => void read(), 1000);
    return () => clearInterval(timer);
  }, [auto, read]);

  return (
    <div className="live-values">
      <div className="row">
        <button className="btn btn-sm" onClick={() => void read()}>Read live values</button>
        <label className="row muted">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> auto refresh
        </label>
      </div>
      {values ? <ValueTable values={values.properties} /> : null}
      {Object.entries(values?.pads ?? {}).map(([pad, padValues]) => (
        <div key={pad}>
          <div className="muted mono">pad {pad}</div>
          <ValueTable values={padValues} />
        </div>
      ))}
    </div>
  );
}

function ValueTable({ values }: { values: Record<string, PropertyValue | null> }) {
  return (
    <table className="kv-table">
      <tbody>
        {Object.entries(values).map(([name, value]) => (
          <tr key={name}>
            <td className="mono">{name}</td>
            <td className="mono">{value === null ? "—" : String(value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
