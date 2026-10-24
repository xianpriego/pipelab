// What the rule/action editors can offer in their selects and "$" autocomplete.

import { createContext, useContext } from "react";
import type { ProbeSchema } from "../../api/dynamic";
import { FALLBACK_SCHEMA } from "../../lib/probeSchema";

export interface Choice {
  value: string;
  label: string;
}

export interface RuleEditorContext {
  schema: ProbeSchema;
  /** Element names in scope (set-property, send-event…). */
  nodes: string[];
  /** Custom and built-in API functions. */
  functions: string[];
  slots: Choice[];
  probes: Choice[];
  /** Variables of the rule set being edited (none for API functions). */
  variables: string[];
  /** Arguments of the API function being edited. */
  params: string[];
  /** Writable property names of an element (by name), when known. */
  properties: (node: string) => string[];
}

export const EMPTY_CONTEXT: RuleEditorContext = {
  schema: FALLBACK_SCHEMA, nodes: [], functions: [], slots: [], probes: [], variables: [], params: [],
  properties: () => [],
};

export const RuleEditorCtx = createContext<RuleEditorContext>(EMPTY_CONTEXT);

export function useRuleEditor(): RuleEditorContext {
  return useContext(RuleEditorCtx);
}
