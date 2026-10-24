// Live previews of sinks: last JPEG frame for video, levels for audio.

import { create } from "zustand";
import type { PreviewFrame } from "../api/events";
import { publishAudio } from "../lib/audioBus";
import { pcmFloat32, peakLevels } from "../api/frames";

export interface VideoPreview {
  kind: "video";
  url: string;
  width: number;
  height: number;
  frames: number;
  fps: number;
  lastTime: number;
}

export interface AudioPreview {
  kind: "audio";
  rate: number;
  channels: number;
  levels: number[];
  lastTime: number;
}

export type Preview = VideoPreview | AudioPreview;

const AUDIO_UI_INTERVAL_MS = 66;

interface PreviewStore {
  previews: Record<string, Preview>;
  /** Edge ids whose content is being watched (link taps). */
  taps: string[];
  handleFrame: (frame: PreviewFrame, now?: number) => void;
  setTapped: (edgeId: string, tapped: boolean) => void;
  remove: (key: string) => void;
  clear: () => void;
}

function smoothFps(previous: number, intervalMs: number): number {
  if (intervalMs <= 0) return previous;
  const instant = 1000 / intervalMs;
  return previous === 0 ? instant : previous * 0.8 + instant * 0.2;
}

export const usePreviewStore = create<PreviewStore>((set, get) => ({
  previews: {},
  taps: [],
  handleFrame: (frame, now = performance.now()) => {
    const { header, payload } = frame;
    const current = get().previews[header.node_id];
    if (header.kind === "video") {
      const url = URL.createObjectURL(new Blob([payload as BlobPart], { type: header.mime || "image/jpeg" }));
      if (current?.kind === "video") URL.revokeObjectURL(current.url);
      const previous = current?.kind === "video" ? current : null;
      const preview: VideoPreview = {
        kind: "video",
        url,
        width: header.width,
        height: header.height,
        frames: (previous?.frames ?? 0) + 1,
        fps: previous ? smoothFps(previous.fps, now - previous.lastTime) : 0,
        lastTime: now,
      };
      set((state) => ({ previews: { ...state.previews, [header.node_id]: preview } }));
      return;
    }
    const samples = pcmFloat32(payload);
    publishAudio(header.node_id, samples, header.rate, header.channels);
    if (current?.kind === "audio" && now - current.lastTime < AUDIO_UI_INTERVAL_MS) return;
    const preview: AudioPreview = {
      kind: "audio",
      rate: header.rate,
      channels: header.channels,
      levels: peakLevels(samples, header.channels),
      lastTime: now,
    };
    set((state) => ({ previews: { ...state.previews, [header.node_id]: preview } }));
  },
  setTapped: (edgeId, tapped) =>
    set((state) => ({
      taps: tapped ? [...new Set([...state.taps, edgeId])] : state.taps.filter((id) => id !== edgeId),
    })),
  remove: (key) => {
    const preview = get().previews[key];
    if (!preview) return;
    if (preview.kind === "video") URL.revokeObjectURL(preview.url);
    set((state) => {
      const previews = { ...state.previews };
      delete previews[key];
      return { previews };
    });
  },
  clear: () => {
    for (const preview of Object.values(get().previews)) {
      if (preview.kind === "video") URL.revokeObjectURL(preview.url);
    }
    set({ previews: {}, taps: [] });
  },
}));
