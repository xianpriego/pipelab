// Commands on no-code probes: add from templates, send signals while running.

import { api, errorMessage } from "../../api/client";
import type { ProbeRuleSet, ProbeTarget, Value } from "../../api/dynamic";
import type { ProbeTemplate } from "../../lib/probeTemplates";
import { useGraphStore } from "../../store/graphStore";
import { useProjectStore } from "../../store/projectStore";
import { notify } from "../../store/uiStore";

export function addProbeFromTemplate(template: ProbeTemplate, target: ProbeTarget): ProbeRuleSet {
  const graph = useGraphStore.getState().graph;
  const nodeName = target.kind === "node" ? graph.nodes.find((node) => node.id === target.id)?.name : undefined;
  const probe = template.build(target, { nodeName });
  useGraphStore.getState().addProbe(probe);
  return probe;
}

/** Fires the ``signal`` rules named ``name`` of a running probe. */
export async function sendSignal(probe: ProbeRuleSet, name: string, value: Value): Promise<boolean> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return false;
  try {
    const result = await api.runtimeSignal(meta.id, probe.id, name, value);
    if (!result.ok) {
      notify({ level: "error", title: `Signal "${name}" failed`, message: result.error ?? undefined });
      return false;
    }
    notify({ level: "success", title: `Sent "${name}" to ${probe.name}`, timeout: 2500 });
    return true;
  } catch (error) {
    notify({ level: "error", title: `Signal "${name}" failed`, message: errorMessage(error) });
    return false;
  }
}
