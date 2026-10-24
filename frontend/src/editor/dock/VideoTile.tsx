import { useState } from "react";
import { Icon } from "../../components/Icon";
import { usePreviewStore } from "../../store/previewStore";

interface TileProps {
  /** Sink node id, or `edge:<id>` for a link tap. */
  previewKey: string;
  name: string;
  running: boolean;
  onClose?: () => void;
}

export function VideoTile({ previewKey, name, running, onClose }: TileProps) {
  const preview = usePreviewStore((state) => state.previews[previewKey]);
  const [large, setLarge] = useState(false);
  const video = preview?.kind === "video" ? preview : null;
  return (
    <div className={`preview-tile${large ? " large" : ""}`}>
      <div className="preview-tile-head">
        <Icon name="eye" size={13} />
        <span className="mono preview-name" title={name}>{name}</span>
        <span className="spacer" />
        {video ? <span className="faint mono">{video.width}×{video.height} · {video.fps.toFixed(1)} fps</span> : null}
        <button className="icon-btn" onClick={() => setLarge(!large)} aria-label="Toggle size" title="Toggle size">
          <Icon name={large ? "chevronDown" : "chevronUp"} size={13} />
        </button>
        {onClose ? (
          <button className="icon-btn" onClick={onClose} aria-label="Stop watching" title="Stop watching">
            <Icon name="close" size={13} />
          </button>
        ) : null}
      </div>
      <div className="preview-frame">
        {video ? (
          <img src={video.url} alt={`Live output of ${name}`} />
        ) : (
          <span className="faint">{running ? "Waiting for frames…" : "Run the pipeline to see this sink."}</span>
        )}
      </div>
    </div>
  );
}
