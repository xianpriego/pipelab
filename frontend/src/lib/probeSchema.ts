// Static copy of GET /api/probes/schema (docs/DYNAMIC.md §4): fallback and test fixture.

import type { FieldSpec, ProbeSchema, Spec } from "../api/dynamic";

const f = (name: string, kind: FieldSpec["kind"], label: string, required = false): FieldSpec => ({
  name, kind, label, required,
});

export const FALLBACK_SCHEMA: ProbeSchema = {
  triggers: [
    { type: "start", label: "Pipeline starts", description: "Once when the pipeline first reaches PLAYING.", fields: [] },
    { type: "buffer", label: "A buffer passes", description: "Every buffer crossing the watched pads.", fields: [] },
    { type: "event", label: "An event passes", description: "Every matching downstream event.",
      fields: [f("event", "event", "Event", true)] },
    { type: "idle", label: "No data for…", description: "Once when no buffer crossed for this long; re-armed by the next buffer.",
      fields: [f("ms", "ms", "Timeout (ms)", true)] },
    { type: "resumed", label: "Data flows again", description: "First buffer after an idle trigger fired.", fields: [] },
    { type: "interval", label: "Every…", description: "Periodically while running.",
      fields: [f("ms", "ms", "Period (ms)", true)] },
    { type: "property", label: "Property change requested", description: "A live change of the property was requested (intercepted unless a rule passes it).",
      fields: [f("property", "property", "Property", true)] },
    { type: "signal", label: "Signal received", description: "Signal sent from the UI, an API function or another probe.",
      fields: [f("name", "string", "Signal name", true)] },
  ],
  conditions: [
    { type: "keyframe", label: "Is a keyframe", description: "The buffer has no delta-unit flag.", fields: [] },
    { type: "flag", label: "Buffer flag", description: "The buffer carries this flag.", fields: [f("flag", "flag", "Flag", true)] },
    { type: "size", label: "Size", description: "Buffer size in bytes.", fields: [f("op", "op", "Operator", true), f("value", "value", "Bytes", true)] },
    { type: "pts-gap", label: "PTS gap", description: "Milliseconds between consecutive PTS.", fields: [f("op", "op", "Operator", true), f("value", "value", "ms", true)] },
    { type: "pts-backwards", label: "PTS goes backwards", description: "The PTS is lower than the previous one.", fields: [] },
    { type: "every", label: "Every n-th time", description: "Holds on every n-th evaluation of this rule.", fields: [f("n", "int", "n", true)] },
    { type: "rate", label: "Rate", description: "Buffers per second over the last second.", fields: [f("op", "op", "Operator", true), f("value", "value", "Buffers/s", true)] },
    { type: "caps-field", label: "Caps field", description: "A field of the pad's current caps.", fields: [f("field", "string", "Field", true), f("op", "op", "Operator", true), f("value", "value", "Value", true)] },
    { type: "variable", label: "Variable", description: "Compares a probe variable.", fields: [f("name", "string", "Variable", true), f("op", "op", "Operator", true), f("value", "value", "Value", true)] },
    { type: "pad", label: "Pad", description: "Name of the pad the data crosses.", fields: [f("op", "op", "Operator", true), f("value", "value", "Pad", true)] },
    { type: "random", label: "Random", description: "Holds with this probability.", fields: [f("percent", "percent", "Percent", true)] },
  ],
  actions: [
    { type: "pass", label: "Let it pass", description: "Verdict for the buffer/event (default).", fields: [] },
    { type: "drop", label: "Drop it", description: "Drop the buffer/event.", fields: [] },
    { type: "block", label: "Block the flow", description: "Hold data on the watched pad.", fields: [] },
    { type: "unblock", label: "Unblock the flow", description: "Release held data.", fields: [] },
    { type: "remove-probe", label: "Disable this probe", description: "Stop evaluating this rule set.", fields: [] },
    { type: "post-message", label: "Post bus message", description: "Application message the owning software can catch.",
      fields: [f("name", "string", "Message name", true), f("fields", "fields", "Fields")] },
    { type: "set-property", label: "Set property", description: "Like gst-launch; GstPad properties take a pad name.",
      fields: [f("node", "node", "Element", true), f("property", "property", "Property", true), f("value", "value", "Value", true), f("pad", "pad", "Pad (optional)")] },
    { type: "send-event", label: "Send event", description: "Push an event on the watched pad.",
      fields: [f("event", "event", "Event", true), f("direction", "direction", "Direction"), f("pad", "pad", "Pad (optional)"), f("name", "string", "Custom name"), f("fields", "fields", "Custom fields")] },
    { type: "request-keyframe", label: "Request a keyframe", description: "Upstream force-key-unit.", fields: [f("pad", "pad", "Pad (optional)")] },
    { type: "set-variable", label: "Set variable", description: "", fields: [f("name", "string", "Variable", true), f("value", "value", "Value", true)] },
    { type: "increment", label: "Increment variable", description: "", fields: [f("name", "string", "Variable", true), f("by", "float", "By")] },
    { type: "log", label: "Log", description: "Message in the Probe tab; {var} placeholders are expanded.",
      fields: [f("message", "string", "Message", true), f("level", "level", "Level")] },
    { type: "signal", label: "Send signal", description: "Fire signal rules of a probe.",
      fields: [f("probe", "probe", "Probe (default: this one)"), f("name", "string", "Signal", true), f("value", "value", "Value")] },
    { type: "call", label: "Call API function", description: "Call a pipeline function.",
      fields: [f("function", "function", "Function", true), f("args", "args", "Arguments")] },
    { type: "add-instance", label: "Add slot instance", description: "", fields: [f("slot", "slot", "Slot", true), f("params", "params", "Parameters")] },
    { type: "remove-instance", label: "Remove slot instance", description: "", fields: [f("slot", "slot", "Slot", true), f("instance", "instance", "Instance id", true)] },
    { type: "restart-instance", label: "Restart slot instance", description: "", fields: [f("slot", "slot", "Slot", true), f("instance", "instance", "Instance id", true)] },
  ],
  builtins: [
    { name: "$value", description: "Value of the trigger (requested property value, signal value)" },
    { name: "$pad", description: "Name of the pad" },
    { name: "$pts", description: "PTS of the buffer in seconds" },
    { name: "$size", description: "Size of the buffer in bytes" },
    { name: "$time", description: "Seconds since the pipeline started" },
    { name: "$instance", description: "Name of the enclosing component instance" },
    { name: "$node", description: "Name of the probed element" },
    { name: "$idle_ms", description: "Milliseconds without data (idle trigger)" },
  ],
  events: [
    "any", "eos", "caps", "segment", "tag", "flush-start", "flush-stop", "stream-start", "gap", "custom-downstream",
    "force-key-unit", "flush", "custom",
  ],
  flags: ["delta-unit", "discont", "gap", "header", "droppable", "corrupted", "marker", "live", "resync", "sync-after"],
  operators: ["==", "!=", "<", "<=", ">", ">="],
};

export type SpecGroup = "triggers" | "conditions" | "actions";

export function specFor(schema: ProbeSchema, group: SpecGroup, type: string): Spec | undefined {
  return schema[group].find((spec) => spec.type === type);
}
