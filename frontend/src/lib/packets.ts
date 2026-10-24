// "Buffer flow" animation: how many dots travel along a link and how they look.

export type MediaClass = "video" | "audio" | "encoded" | "other";

export interface PacketPlan {
  count: number;
  radius: number;
}

/** Seconds a dot needs to travel a whole link, whatever its length. */
export const PACKET_TRAVEL_SECONDS = 1.2;
const MAX_PACKETS = 6;

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));

/** Density grows with the buffer rate (log scale), size with the bitrate. */
export function packetPlan(fps: number, bitrate: number): PacketPlan {
  if (!(fps > 0)) return { count: 0, radius: 0 };
  const count = clamp(Math.round(1 + Math.log10(fps) * 1.8), 1, MAX_PACKETS);
  const kbps = Math.max(bitrate / 1000, 1);
  const radius = clamp(2 + Math.log10(kbps) * 0.6, 2, 4.5);
  return { count, radius: Math.round(radius * 10) / 10 };
}

/** Colour family of the data on a link, from its negotiated caps. */
export function mediaClass(caps: string | undefined): MediaClass {
  if (!caps) return "other";
  const name = caps.split(/[,(\s]/, 1)[0];
  if (name === "video/x-raw" || name === "image/x-raw") return "video";
  if (name === "audio/x-raw") return "audio";
  if (/^(video|audio|image)\//.test(name) || name === "application/x-rtp") return "encoded";
  return "other";
}
