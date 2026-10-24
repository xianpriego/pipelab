import { useMemo, useState } from "react";
import { searchElements } from "../../lib/search";
import { useCatalogStore } from "../../store/catalogStore";
import { applyFix } from "../actions";

const QUICK = ["queue", "capsfilter", "videoconvert", "audioconvert", "identity", "tee"];

export function InsertOnEdge({ edgeId }: { edgeId: string }) {
  const elements = useCatalogStore((state) => state.elements);
  const byName = useCatalogStore((state) => state.byName);
  const [query, setQuery] = useState("");
  const results = useMemo(
    () => (query.trim() ? searchElements(elements, { query, categories: [], families: [] }).slice(0, 8) : []),
    [elements, query],
  );

  const insert = (factory: string) => {
    void applyFix({ kind: "insert_on_edge", edge_id: edgeId, elements: [{ factory, properties: {} }] });
    setQuery("");
  };

  return (
    <div className="insert-on-edge">
      <div className="row wrap">
        {QUICK.filter((name) => byName[name]).map((name) => (
          <button key={name} className="chip" onClick={() => insert(name)}>+ {name}</button>
        ))}
      </div>
      <input className="input" placeholder="Search an element to insert…" value={query}
        onChange={(event) => setQuery(event.target.value)} aria-label="Element to insert"
        onKeyDown={(event) => event.key === "Enter" && results[0] && insert(results[0].name)} />
      {results.length ? (
        <ul className="insert-results">
          {results.map((element) => (
            <li key={element.name}>
              <button className="btn btn-ghost btn-sm" onClick={() => insert(element.name)}>
                <span className="mono">{element.name}</span>
                <span className="faint">{element.long_name}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
