// Ready-made probe rule sets to start from (they are plain data: edit them freely).

import type { ProbeRuleSet, ProbeTarget } from "../api/dynamic";
import { createRuleSet, newRule } from "./probeRules";

export interface TemplateContext {
  /** Name of the target element (node targets) used by set-property actions. */
  nodeName?: string;
}

export interface ProbeTemplate {
  id: string;
  name: string;
  description: string;
  kinds: ProbeTarget["kind"][];
  /** Factories it is meant for (empty: any). */
  factories: string[];
  build: (target: ProbeTarget, ctx: TemplateContext) => ProbeRuleSet;
}

function make(target: ProbeTarget, name: string, patch: Partial<ProbeRuleSet>): ProbeRuleSet {
  return { ...createRuleSet(target, name), ...patch };
}

export const PROBE_TEMPLATES: ProbeTemplate[] = [
  {
    id: "watchdog", name: "Watchdog", kinds: ["edge", "node"], factories: [],
    description: "Posts branch-down on the bus when no buffer flows for 2 s, branch-up when data comes back.",
    build: (target) => make(target, "Watchdog", {
      rules: [
        { ...newRule({ type: "idle", ms: 2000 }), actions: [
          { type: "post-message", name: "branch-down", fields: { node: "$node", instance: "$instance", idle_ms: "$idle_ms" } },
          { type: "log", message: "no buffers for {idle_ms} ms", level: "warning" },
        ] },
        { ...newRule({ type: "resumed" }), actions: [
          { type: "post-message", name: "branch-up", fields: { node: "$node", instance: "$instance" } },
          { type: "log", message: "data flows again", level: "info" },
        ] },
      ],
    }),
  },
  {
    id: "keyframe-switch", name: "Keyframe switch", kinds: ["node"], factories: ["input-selector", "output-selector"],
    description: "Selecting another pad waits for its next keyframe (and requests one upstream).",
    build: (target, ctx) => make(target, "Keyframe switch", {
      variables: { target: "" },
      rules: [
        { ...newRule({ type: "property", property: "active-pad" }), actions: [
          { type: "set-variable", name: "target", value: "$value" },
          { type: "request-keyframe", pad: "$value" },
          { type: "log", message: "switch to {target} requested, waiting for a keyframe", level: "info" },
        ] },
        { ...newRule({ type: "buffer" }),
          conditions: [{ type: "keyframe" }, { type: "pad", op: "==", value: "$target" }],
          actions: [
            { type: "set-property", node: ctx.nodeName ?? "", property: "active-pad", value: "$target" },
            { type: "log", message: "switched to {target} on a keyframe", level: "info" },
            { type: "set-variable", name: "target", value: "" },
          ] },
      ],
    }),
  },
  {
    id: "drop-until-keyframe", name: "Drop until keyframe", kinds: ["edge"], factories: [],
    description: "Drops delta frames until the first keyframe; waits again after a flush.",
    build: (target) => make(target, "Drop until keyframe", {
      variables: { synced: false },
      rules: [
        { ...newRule({ type: "buffer" }),
          conditions: [{ type: "variable", name: "synced", op: "==", value: false }, { type: "keyframe" }],
          actions: [{ type: "set-variable", name: "synced", value: true }, { type: "log", message: "first keyframe" }] },
        { ...newRule({ type: "buffer" }),
          conditions: [{ type: "variable", name: "synced", op: "==", value: false }], actions: [{ type: "drop" }] },
        { ...newRule({ type: "event", event: "flush-stop" }), actions: [{ type: "set-variable", name: "synced", value: false }] },
      ],
    }),
  },
  {
    id: "packet-loss", name: "Packet loss", kinds: ["edge"], factories: [],
    description: "Drops a random 5 % of the buffers to test how receivers cope.",
    build: (target) => make(target, "Packet loss", {
      rules: [{ ...newRule({ type: "buffer" }), conditions: [{ type: "random", percent: 5 }], actions: [{ type: "drop" }] }],
    }),
  },
  {
    id: "gate", name: "Gate", kinds: ["edge"], factories: [],
    description: "Signals open/close the link; reopening requests a keyframe.",
    build: (target) => make(target, "Gate", {
      variables: { open: true },
      rules: [
        { ...newRule({ type: "signal", name: "open" }), actions: [
          { type: "set-variable", name: "open", value: true }, { type: "request-keyframe" }, { type: "log", message: "gate open" },
        ] },
        { ...newRule({ type: "signal", name: "close" }), actions: [
          { type: "set-variable", name: "open", value: false }, { type: "log", message: "gate closed" },
        ] },
        { ...newRule({ type: "buffer" }), conditions: [{ type: "variable", name: "open", op: "==", value: false }],
          actions: [{ type: "drop" }] },
      ],
    }),
  },
  {
    id: "rate-alarm", name: "Rate alarm", kinds: ["edge"], factories: [],
    description: "Posts low-rate on the bus when fewer than 20 buffers/s cross the link.",
    build: (target) => make(target, "Rate alarm", {
      rules: [{ ...newRule({ type: "interval", ms: 1000 }), conditions: [{ type: "rate", op: "<", value: 20 }],
        actions: [{ type: "post-message", name: "low-rate", fields: { node: "$node", instance: "$instance" } }] }],
    }),
  },
  {
    id: "eos-after", name: "EOS after N s", kinds: ["edge"], factories: [],
    description: "Sends EOS downstream after 10 s (finalises recordings), then disables itself.",
    build: (target) => make(target, "EOS after 10 s", {
      rules: [{ ...newRule({ type: "interval", ms: 10000 }), actions: [
        { type: "send-event", event: "eos", direction: "downstream" }, { type: "log", message: "EOS sent" }, { type: "remove-probe" },
      ] }],
    }),
  },
  {
    id: "blank", name: "Blank probe", kinds: ["edge", "node"], factories: [],
    description: "Start from an empty rule.",
    build: (target) => make(target, "Probe", { rules: [newRule({ type: "buffer" })] }),
  },
];

/** Templates applicable to a target kind (and factory when restricted). */
export function templatesFor(kind: ProbeTarget["kind"], factory?: string): ProbeTemplate[] {
  return PROBE_TEMPLATES.filter(
    (template) =>
      template.kinds.includes(kind) &&
      (template.factories.length === 0 || (factory !== undefined && template.factories.includes(factory))),
  );
}
