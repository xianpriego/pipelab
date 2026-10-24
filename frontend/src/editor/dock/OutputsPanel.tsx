import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { MediaFile } from "../../api/types";
import { Icon } from "../../components/Icon";
import { formatBytes, formatDate } from "../../lib/format";
import { useRuntimeStore } from "../../store/runtimeStore";
import { notify } from "../../store/uiStore";
import { MediaPlayer } from "./MediaPlayer";

export function OutputsPanel() {
  const [files, setFiles] = useState<MediaFile[]>([]);
  const [selected, setSelected] = useState<MediaFile | null>(null);
  const [uploading, setUploading] = useState(false);
  const runtimeState = useRuntimeStore((state) => state.state);
  const eos = useRuntimeStore((state) => state.eos);
  const input = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listMedia();
      setFiles([...list].sort((a, b) => String(b.modified).localeCompare(String(a.modified))));
    } catch (error) {
      notify({ level: "error", title: "Cannot list media files", message: errorMessage(error) });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, runtimeState, eos]);

  const upload = async (file: File) => {
    setUploading(true);
    try {
      await api.uploadMedia(file);
      notify({ level: "success", title: `Uploaded ${file.name}`, message: "Use it with filesrc location or a file:// URI." });
      await refresh();
    } catch (error) {
      notify({ level: "error", title: "Upload failed", message: errorMessage(error) });
    } finally {
      setUploading(false);
    }
  };

  const remove = async (file: MediaFile) => {
    if (!window.confirm(`Delete ${file.path}?`)) return;
    await api.deleteMedia(file.path).catch((error) => notify({ level: "error", title: "Delete failed", message: errorMessage(error) }));
    if (selected?.path === file.path) setSelected(null);
    await refresh();
  };

  return (
    <div className="outputs-panel">
      <div className="outputs-list">
        <div className="panel-toolbar">
          <button className="btn btn-sm" onClick={() => void refresh()}><Icon name="refresh" size={12} /> Refresh</button>
          <button className="btn btn-sm" disabled={uploading} onClick={() => input.current?.click()}>
            <Icon name="upload" size={12} /> {uploading ? "Uploading…" : "Upload input"}
          </button>
          <input ref={input} type="file" hidden onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])} />
        </div>
        <div className="muted outputs-hint">Relative paths (e.g. <code>location=out.mp4</code>) are written to the media folder.</div>
        {files.length === 0 ? <div className="empty-state">No files yet.</div> : null}
        {files.map((file) => (
          <div key={file.path} className={`output-row${selected?.path === file.path ? " selected" : ""}`}
            onClick={() => setSelected(file)}>
            <Icon name="file" size={13} />
            <span className="mono output-name">{file.path}</span>
            <span className="faint">{formatBytes(file.size)}</span>
            <span className="faint nowrap">{formatDate(file.modified)}</span>
            <a className="icon-btn" href={api.mediaUrl(file.path)} download onClick={(e) => e.stopPropagation()}
              title="Download" aria-label="Download">
              <Icon name="download" size={13} />
            </a>
            <button className="icon-btn" title="Delete" aria-label="Delete" onClick={(e) => {
              e.stopPropagation();
              void remove(file);
            }}>
              <Icon name="trash" size={13} />
            </button>
          </div>
        ))}
      </div>
      <div className="outputs-player">
        {selected ? <MediaPlayer file={selected} /> : <span className="faint">Select a file to play it here.</span>}
      </div>
    </div>
  );
}
