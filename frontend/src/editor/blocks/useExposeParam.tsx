import { useState, type ReactNode } from "react";
import type { GraphNode, PropertyInfo } from "../../api/types";
import { Icon } from "../../components/Icon";
import { paramOf } from "../../lib/components";
import { useCurrentSession } from "../../store/componentStore";
import { ExposeParamDialog } from "./ExposeParamDialog";

interface Exposer {
  /** Row control: the parameter driving the property, or a button to expose it. Undefined outside components. */
  extra: ((prop: PropertyInfo, pad?: string) => ReactNode) | undefined;
  dialog: ReactNode;
}

/** "Expose as parameter" on the property rows of an element inside a component. */
export function useExposeParam(node: GraphNode | undefined): Exposer {
  const session = useCurrentSession();
  const [exposing, setExposing] = useState<{ prop: PropertyInfo; pad: string | null } | null>(null);
  if (!session || !node) return { extra: undefined, dialog: null };

  const extra = (prop: PropertyInfo, pad?: string) => {
    if (!prop.writable) return null;
    const param = paramOf(session.parameters, node.id, prop.name, pad ?? null);
    if (param) {
      return <span className="param-chip mono" title={`Set by the component parameter "${param}"`}>${param}</span>;
    }
    return (
      <button className="icon-btn expose-btn" aria-label={`Expose ${prop.name} as parameter`} title="Expose as parameter"
        onClick={() => setExposing({ prop, pad: pad ?? null })}>
        <Icon name="export" size={11} />
      </button>
    );
  };
  const dialog = exposing ? (
    <ExposeParamDialog node={node} prop={exposing.prop} pad={exposing.pad} onClose={() => setExposing(null)} />
  ) : null;
  return { extra, dialog };
}
