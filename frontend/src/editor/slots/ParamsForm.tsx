import type { Value } from "../../api/dynamic";
import type { PropertyInfo, PropertyValue } from "../../api/types";
import { useElementDetails } from "../../hooks/useElementDetails";
import { COMPONENT_PREFIX } from "../../lib/components";
import { PropertyList } from "../inspector/PropertyList";
import { KeyValueEditor } from "../rules/KeyValueEditor";

interface ParamsFormProps {
  component: string;
  params: Record<string, Value>;
  onChange: (params: Record<string, Value>) => void;
  label: string;
}

function asValues(params: Record<string, Value>): Record<string, PropertyValue> {
  return Object.fromEntries(Object.entries(params).filter((entry): entry is [string, PropertyValue] => entry[1] !== null));
}

/** Typed form of a component's parameters (its virtual element properties); free keys when unknown. */
export function ParamsForm({ component, params, onChange, label }: ParamsFormProps) {
  const details = useElementDetails(`${COMPONENT_PREFIX}${component}`);
  if (!details) return <KeyValueEditor value={params} onChange={onChange} label={label} />;
  const writable = details.properties.filter((prop) => prop.writable && prop.name !== "name");
  if (writable.length === 0) return <p className="muted">This component has no parameters.</p>;

  const change = (prop: PropertyInfo, value: PropertyValue | undefined) => {
    const next = { ...params };
    if (value === undefined) delete next[prop.name];
    else next[prop.name] = value;
    onChange(next);
  };
  return (
    <div className="params-form" aria-label={label}>
      <PropertyList properties={writable} values={asValues(params)} running={false} pads={[]} searchable={false}
        onChange={change} onTryLive={() => undefined} />
    </div>
  );
}
