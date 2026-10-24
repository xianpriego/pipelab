import { useEffect, useMemo } from "react";
import type { Value } from "../../api/dynamic";
import { functionsOf } from "../../lib/apiFunctions";
import { probesOf } from "../../lib/probeRules";
import { slotsOf } from "../../lib/slots";
import { useCatalogStore } from "../../store/catalogStore";
import { useGraphStore } from "../../store/graphStore";
import { useSchemaStore } from "../../store/schemaStore";
import type { RuleEditorContext } from "./editorContext";

/** Choices offered by rule/action editors for the graph being edited. */
export function useEditorContext(variables: Record<string, Value> = {}, params: string[] = []): RuleEditorContext {
  const graph = useGraphStore((state) => state.graph);
  const schema = useSchemaStore((state) => state.schema);
  const details = useCatalogStore((state) => state.details);
  const loadDetails = useCatalogStore((state) => state.loadDetails);

  useEffect(() => {
    void useSchemaStore.getState().load();
  }, []);

  return useMemo(() => {
    const factoryOf = (name: string) => graph.nodes.find((node) => node.name === name)?.factory;
    const slots = slotsOf(graph);
    return {
      schema,
      nodes: graph.nodes.map((node) => node.name),
      functions: [
        ...functionsOf(graph).map((fn) => fn.name),
        ...slots.flatMap((slot) => [`add_${slot.item}`, `remove_${slot.item}`, `restart_${slot.item}`, `list_${slot.name}`]),
      ],
      slots: slots.map((slot) => ({ value: slot.id, label: `${slot.name} (${slot.component})` })),
      probes: probesOf(graph).map((probe) => ({ value: probe.id, label: probe.name })),
      variables: Object.keys(variables),
      params,
      properties: (name: string) => {
        const factory = factoryOf(name);
        if (!factory) return [];
        const info = details[factory];
        if (!info) {
          void loadDetails(factory);
          return [];
        }
        return info.properties.filter((prop) => prop.writable).map((prop) => prop.name);
      },
    };
  }, [graph, schema, details, loadDetails, variables, params]);
}
