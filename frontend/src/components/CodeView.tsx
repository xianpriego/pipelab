import { useMemo, type ReactNode } from "react";
import { highlightLine } from "../lib/highlight";

interface CodeViewProps {
  code: string;
  language: string;
}

export function CodeView({ code, language }: CodeViewProps) {
  const lines = useMemo<ReactNode[]>(
    () => code.split("\n").map((line) => highlightLine(line, language)),
    [code, language],
  );
  return (
    <pre className="code-view" data-language={language}>
      <code>
        {lines.map((line, index) => (
          <span className="line" key={index}>
            {line}
            {"\n"}
          </span>
        ))}
      </code>
    </pre>
  );
}
