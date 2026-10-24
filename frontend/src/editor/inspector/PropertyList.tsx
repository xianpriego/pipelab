import { useMemo, useState, type ReactNode } from "react";
import type { PropertyInfo, PropertyValue } from "../../api/types";
import { PropertyField } from "./PropertyField";

interface PropertyListProps {
  properties: PropertyInfo[];
  values: Record<string, PropertyValue>;
  running: boolean;
  pads: string[];
  onChange: (prop: PropertyInfo, value: PropertyValue | undefined) => void;
  onTryLive: (prop: PropertyInfo) => void;
  searchable?: boolean;
  /** Values a script deferred, by property name. */
  pending?: Record<string, PropertyValue>;
  /** Extra controls in each row's head (e.g. "expose as parameter" inside a component). */
  extra?: (prop: PropertyInfo) => ReactNode;
}

export function PropertyList({
  properties, values, running, pads, onChange, onTryLive, searchable = true, pending, extra,
}: PropertyListProps) {
  const [query, setQuery] = useState("");
  const [showReadOnly, setShowReadOnly] = useState(false);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return properties.filter((prop) => {
      if (!prop.writable && !showReadOnly) return false;
      if (!q) return true;
      return prop.name.includes(q) || prop.blurb.toLowerCase().includes(q);
    });
  }, [properties, query, showReadOnly]);
  const hiddenReadOnly = properties.filter((p) => !p.writable).length;

  return (
    <div className="property-list">
      {searchable ? (
        <div className="row property-tools">
          <input className="input" placeholder={`Filter ${properties.length} properties…`} value={query}
            onChange={(event) => setQuery(event.target.value)} aria-label="Filter properties" />
          {hiddenReadOnly > 0 ? (
            <label className="row muted nowrap" title="Show read-only properties">
              <input type="checkbox" checked={showReadOnly} onChange={(e) => setShowReadOnly(e.target.checked)} />
              read-only
            </label>
          ) : null}
        </div>
      ) : null}
      {visible.map((prop) => (
        <PropertyField
          key={prop.name}
          prop={prop}
          value={values[prop.name]}
          running={running}
          pads={pads}
          pending={pending?.[prop.name]}
          onChange={(value) => onChange(prop, value)}
          onTryLive={() => onTryLive(prop)}
          extra={extra?.(prop)}
        />
      ))}
      {visible.length === 0 ? <div className="muted">No properties match.</div> : null}
    </div>
  );
}
