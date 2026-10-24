import { useEffect, useRef } from "react";
import { api } from "../../api/client";
import type { MediaFile } from "../../api/types";
import { mediaKind } from "../../lib/mediaKind";

function HlsVideo({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const video = ref.current;
    if (!video) return undefined;
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src;
      return undefined;
    }
    let destroyed = false;
    let destroy = () => undefined as void;
    void import("hls.js").then(({ default: Hls }) => {
      if (destroyed || !Hls.isSupported()) return;
      const hls = new Hls();
      hls.loadSource(src);
      hls.attachMedia(video);
      destroy = () => hls.destroy();
    });
    return () => {
      destroyed = true;
      destroy();
    };
  }, [src]);
  return <video ref={ref} controls autoPlay muted />;
}

export function MediaPlayer({ file }: { file: MediaFile }) {
  const url = `${api.mediaUrl(file.path)}?v=${encodeURIComponent(String(file.modified))}`;
  switch (mediaKind(file.path, file.mime)) {
    case "video":
      return <video key={url} src={url} controls autoPlay muted />;
    case "audio":
      return <audio key={url} src={url} controls />;
    case "image":
      return <img src={url} alt={file.path} />;
    case "hls":
      return <HlsVideo src={url} />;
    case "text":
      return <iframe title={file.path} src={url} />;
    default:
      return <div className="muted">No inline preview for this file type. Use download.</div>;
  }
}
