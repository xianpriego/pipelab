// Decoder of binary preview frames: u32 BE header length | header JSON | payload.

import type { FrameHeader, PreviewFrame } from "./events";

const decoder = new TextDecoder();

export function decodeFrame(buffer: ArrayBuffer): PreviewFrame | null {
  if (buffer.byteLength < 4) return null;
  const headerLength = new DataView(buffer).getUint32(0, false);
  if (4 + headerLength > buffer.byteLength) return null;
  let header: unknown;
  try {
    header = JSON.parse(decoder.decode(new Uint8Array(buffer, 4, headerLength)));
  } catch {
    return null;
  }
  if (!isFrameHeader(header)) return null;
  return { header, payload: new Uint8Array(buffer, 4 + headerLength) };
}

function isFrameHeader(value: unknown): value is FrameHeader {
  if (typeof value !== "object" || value === null) return false;
  const { kind, node_id } = value as { kind?: unknown; node_id?: unknown };
  return (kind === "video" || kind === "audio") && typeof node_id === "string";
}

/** Encoder counterpart, used by tests and local tooling. */
export function encodeFrame(header: FrameHeader, payload: Uint8Array): ArrayBuffer {
  const headerBytes = new TextEncoder().encode(JSON.stringify(header));
  const buffer = new ArrayBuffer(4 + headerBytes.length + payload.length);
  new DataView(buffer).setUint32(0, headerBytes.length, false);
  new Uint8Array(buffer, 4, headerBytes.length).set(headerBytes);
  new Uint8Array(buffer, 4 + headerBytes.length).set(payload);
  return buffer;
}

/** Interleaved little-endian float32 samples (copies to guarantee alignment). */
export function pcmFloat32(payload: Uint8Array): Float32Array {
  const samples = Math.floor(payload.byteLength / 4);
  const copy = new ArrayBuffer(samples * 4);
  new Uint8Array(copy).set(payload.subarray(0, samples * 4));
  return new Float32Array(copy);
}

/** Peak level per channel (0..1) of interleaved samples. */
export function peakLevels(samples: Float32Array, channels: number): number[] {
  const peaks = new Array<number>(Math.max(channels, 1)).fill(0);
  for (let i = 0; i < samples.length; i += 1) {
    const channel = i % peaks.length;
    const value = Math.abs(samples[i]);
    if (value > peaks[channel]) peaks[channel] = value;
  }
  return peaks.map((peak) => Math.min(peak, 1));
}
