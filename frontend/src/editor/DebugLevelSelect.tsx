import { useProjectStore } from "../store/projectStore";

const LEVELS: [string, string][] = [
  ["*:1", "Errors"],
  ["*:2", "Warnings"],
  ["*:3", "Fixme"],
  ["*:4", "Info"],
  ["*:5", "Debug (verbose)"],
];

export function DebugLevelSelect() {
  const settings = useProjectStore((state) => state.meta?.settings);
  const setSettings = useProjectStore((state) => state.setSettings);
  if (!settings) return null;
  const known = LEVELS.some(([value]) => value === settings.gst_debug);
  return (
    <label className="debug-select" title="GST_DEBUG used when the pipeline starts">
      <span className="muted">GST_DEBUG</span>
      <select
        className="select"
        value={settings.gst_debug}
        onChange={(event) => setSettings({ ...settings, gst_debug: event.target.value })}
      >
        {LEVELS.map(([value, label]) => (
          <option key={value} value={value}>
            {value} · {label}
          </option>
        ))}
        {!known ? <option value={settings.gst_debug}>{settings.gst_debug}</option> : null}
      </select>
    </label>
  );
}
