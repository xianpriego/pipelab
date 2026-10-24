import type { ElementInfo } from "../../api/types";
import { elementDocsUrl } from "../../lib/docs";
import { useCatalogStore } from "../../store/catalogStore";

export function ElementInfoSection({ info }: { info: ElementInfo }) {
  const catalog = useCatalogStore((state) => state.elements);
  const rows: [string, string][] = [
    ["Klass", info.klass],
    ["Plugin", `${info.plugin} (${info.source || info.family})`],
    ["Package", info.package],
    ["Rank", String(info.rank)],
    ["Author", info.author],
    ["Origin", info.origin],
    ["Hierarchy", info.hierarchy.join(" → ")],
    ["Interfaces", info.interfaces.join(", ") || "—"],
    ["URI", info.uri_type ? `${info.uri_type}: ${info.uri_protocols.join(", ")}` : "—"],
  ];
  return (
    <>
      <dl className="info-list">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value || "—"}</dd>
          </div>
        ))}
      </dl>
      <a className="docs-link" href={elementDocsUrl(info, catalog)} target="_blank" rel="noreferrer">
        GStreamer documentation ↗
      </a>
    </>
  );
}
