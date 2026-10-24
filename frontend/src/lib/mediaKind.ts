// What kind of inline player suits a media file.

export type MediaKind = "video" | "audio" | "image" | "hls" | "text" | "other";

const EXT: Record<string, MediaKind> = {
  mp4: "video", m4v: "video", webm: "video", mkv: "video", mov: "video", ogv: "video",
  wav: "audio", mp3: "audio", ogg: "audio", oga: "audio", opus: "audio", flac: "audio", aac: "audio", m4a: "audio",
  jpg: "image", jpeg: "image", png: "image", gif: "image", webp: "image", bmp: "image", svg: "image",
  m3u8: "hls", txt: "text", log: "text", json: "text", srt: "text", vtt: "text", csv: "text",
};

export function mediaKind(path: string, mime?: string | null): MediaKind {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  if (EXT[ext]) return EXT[ext];
  if (mime?.startsWith("video/")) return "video";
  if (mime?.startsWith("audio/")) return "audio";
  if (mime?.startsWith("image/")) return "image";
  return "other";
}
