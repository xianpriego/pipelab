// Minimal inline SVG icon set (stroke icons, 16px grid).

const PATHS: Record<string, string> = {
  play: "M5 3.5v9l7.5-4.5z",
  pause: "M5 3.5v9M11 3.5v9",
  stop: "M4 4h8v8H4z",
  kill: "M4 4l8 8M12 4l-8 8",
  back: "M10 3L5 8l5 5",
  plus: "M8 3v10M3 8h10",
  trash: "M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 8.5h5.6l.7-8.5",
  copy: "M5.5 5.5h7v7h-7zM3.5 10.5v-7h7",
  layout: "M2.5 3h4v4h-4zM9.5 3h4v4h-4zM6 10h4v4H6zM4.5 7v1.5h7V7M8 8.5V10",
  export: "M8 10V2.5M5 5.5l3-3 3 3M3 10v3.5h10V10",
  import: "M8 2.5V10M5 7l3 3 3-3M3 10v3.5h10V10",
  graph: "M3 8h3M10 8h3M6 5.5h4v5H6zM13 8V4M13 8v4",
  sun: "M8 5.2a2.8 2.8 0 100 5.6 2.8 2.8 0 000-5.6zM8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1",
  moon: "M12.5 9.5A5 5 0 016.5 3.5a5 5 0 106 6z",
  eye: "M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8zM8 6.2a1.8 1.8 0 100 3.6 1.8 1.8 0 000-3.6z",
  speaker: "M2.5 6h2.5l3.5-3v10L5 10H2.5zM11 5.5a3.5 3.5 0 010 5M12.8 3.8a6 6 0 010 8.4",
  search: "M7 2.5a4.5 4.5 0 100 9 4.5 4.5 0 000-9zM10.3 10.3l3.2 3.2",
  refresh: "M13 3.5v3h-3M3 12.5v-3h3M12.4 6.5A4.8 4.8 0 003.8 5M3.6 9.5a4.8 4.8 0 008.6 1.5",
  upload: "M8 11V3M5 6l3-3 3 3M3 13h10",
  download: "M8 3v8M5 8l3 3 3-3M3 13h10",
  warning: "M8 2.5l6 11H2zM8 6.5v3M8 11.5v.5",
  error: "M8 2a6 6 0 100 12A6 6 0 008 2zM6 6l4 4M10 6l-4 4",
  info: "M8 2a6 6 0 100 12A6 6 0 008 2zM8 7.5v4M8 5v.5",
  check: "M3 8.5l3 3 7-7",
  chevronDown: "M4 6l4 4 4-4",
  chevronUp: "M4 10l4-4 4 4",
  chevronRight: "M6 4l4 4-4 4",
  flow: "M1.5 8h13M4.5 6.6a1.4 1.4 0 100 2.8 1.4 1.4 0 000-2.8zM10.5 6.6a1.4 1.4 0 100 2.8 1.4 1.4 0 000-2.8z",
  close: "M4 4l8 8M12 4l-8 8",
  zap: "M9 1.5L3.5 9H8l-1 5.5L12.5 7H8z",
  bolt: "M9 1.5L3.5 9H8l-1 5.5L12.5 7H8z",
  file: "M4 1.5h5l3 3v10H4zM9 1.5v3h3",
  save: "M3 2.5h8l2 2v9H3zM5 2.5v3h5v-3M5 13.5v-4h6v4",
};

export type IconName = keyof typeof PATHS;

interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
  title?: string;
}

const FILLED = new Set<IconName>(["play", "stop", "zap", "bolt"]);

export function Icon({ name, size = 16, className, title }: IconProps) {
  const filled = FILLED.has(name);
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      className={className}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={filled ? 1 : 1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
    >
      {title ? <title>{title}</title> : null}
      <path d={PATHS[name]} />
    </svg>
  );
}
