// Tiny single-line syntax highlighter for exported code (no dependencies).

import type { ReactNode } from "react";

const KEYWORDS: Record<string, string[]> = {
  python: ["def", "class", "return", "import", "from", "if", "elif", "else", "for", "in", "while", "try",
    "except", "finally", "with", "as", "None", "True", "False", "self", "not", "and", "or", "lambda", "pass",
    "raise", "global", "is", "del", "yield"],
  c: ["int", "void", "char", "static", "const", "return", "if", "else", "for", "while", "struct", "typedef",
    "gboolean", "gchar", "gint", "guint", "gpointer", "NULL", "TRUE", "FALSE", "include", "sizeof", "break"],
  rust: ["fn", "let", "mut", "use", "pub", "struct", "impl", "match", "if", "else", "for", "in", "while",
    "return", "Some", "None", "Ok", "Err", "move", "as", "loop", "break", "mod", "crate", "self", "enum"],
  shell: ["gst-launch-1.0"],
  json: ["true", "false", "null"],
};

const COMMENT_PREFIX: Record<string, string[]> = {
  python: ["#"], shell: ["#"], c: ["//", "/*", " *"], rust: ["//"], json: [],
};

const TOKEN = /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\b\d+(?:\.\d+)?\b|[A-Za-z_][\w-]*)/g;

function normalize(language: string): string {
  if (language === "bash" || language === "sh") return "shell";
  if (language === "cpp") return "c";
  return language;
}

export function highlightLine(line: string, language: string): ReactNode {
  const lang = normalize(language);
  const trimmed = line.trimStart();
  if ((COMMENT_PREFIX[lang] ?? []).some((prefix) => trimmed.startsWith(prefix))) {
    return <span className="tok-comment">{line}</span>;
  }
  const keywords = new Set(KEYWORDS[lang] ?? []);
  const parts: ReactNode[] = [];
  let last = 0;
  for (const match of line.matchAll(TOKEN)) {
    const token = match[0];
    const index = match.index ?? 0;
    let className: string | null = null;
    if (token.startsWith('"') || token.startsWith("'")) className = "tok-string";
    else if (/^\d/.test(token)) className = "tok-number";
    else if (keywords.has(token)) className = "tok-keyword";
    if (!className) continue;
    if (index > last) parts.push(line.slice(last, index));
    parts.push(
      <span key={index} className={className}>
        {token}
      </span>,
    );
    last = index + token.length;
  }
  if (last < line.length) parts.push(line.slice(last));
  return parts;
}
