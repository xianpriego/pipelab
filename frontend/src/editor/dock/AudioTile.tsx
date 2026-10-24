import { useEffect, useState } from "react";
import { Icon } from "../../components/Icon";
import { subscribeAudio } from "../../lib/audioBus";
import { PcmPlayer } from "../../lib/pcmPlayer";
import { usePreviewStore } from "../../store/previewStore";

interface TileProps {
  /** Sink node id, or `edge:<id>` for a link tap. */
  previewKey: string;
  name: string;
  running: boolean;
  onClose?: () => void;
}

function toDb(level: number): number {
  return level <= 0 ? -60 : Math.max(-60, 20 * Math.log10(level));
}

export function AudioTile({ previewKey, name, running, onClose }: TileProps) {
  const preview = usePreviewStore((state) => state.previews[previewKey]);
  const [listening, setListening] = useState(false);
  const audio = preview?.kind === "audio" ? preview : null;

  useEffect(() => {
    if (!listening) return undefined;
    const player = new PcmPlayer();
    const unsubscribe = subscribeAudio(previewKey, (samples, rate, channels) => player.push(samples, rate, channels));
    return () => {
      unsubscribe();
      player.close();
    };
  }, [listening, previewKey]);

  return (
    <div className="preview-tile audio">
      <div className="preview-tile-head">
        <Icon name="speaker" size={13} />
        <span className="mono preview-name" title={name}>{name}</span>
        <span className="spacer" />
        {audio ? <span className="faint mono">{audio.rate} Hz · {audio.channels} ch</span> : null}
        {onClose ? (
          <button className="icon-btn" onClick={onClose} aria-label="Stop watching" title="Stop watching">
            <Icon name="close" size={13} />
          </button>
        ) : null}
      </div>
      <div className="vu-meters">
        {(audio?.levels ?? [0, 0]).map((level, channel) => {
          const db = toDb(level);
          return (
            <div key={channel} className="vu-row">
              <span className="faint mono">{channel + 1}</span>
              <div className="vu-bar">
                <div className={db > -3 ? "hot" : db > -12 ? "warm" : ""} style={{ width: `${((db + 60) / 60) * 100}%` }} />
              </div>
              <span className="faint mono vu-db">{db.toFixed(0)} dB</span>
            </div>
          );
        })}
      </div>
      <button className={`btn btn-sm${listening ? " btn-primary" : ""}`} disabled={!running && !listening}
        onClick={() => setListening(!listening)}>
        <Icon name="speaker" size={12} /> {listening ? "Listening" : "Listen"}
      </button>
    </div>
  );
}
