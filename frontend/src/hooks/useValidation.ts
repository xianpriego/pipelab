import { useEffect } from "react";
import { ApiError, api, errorMessage } from "../api/client";
import { useCatalogStore } from "../store/catalogStore";
import { draftDefinition, useComponentStore } from "../store/componentStore";
import { useGraphStore } from "../store/graphStore";
import { useValidationStore } from "../store/validationStore";

const DEBOUNCE_MS = 400;

/** Re-validates the graph (debounced) whenever it changes. */
export function useValidation(loaded: boolean): void {
  const revision = useGraphStore((state) => state.revision);
  // Port and parameter edits change what the component validation reports.
  const session = useComponentStore((state) => state.sessions.at(-1));
  const catalogReady = useCatalogStore((state) => state.state === "ready");
  const scopeKey = useComponentStore((state) => state.sessions.map((s) => s.base.id).join("/"));

  // Issues of the previous scope (project or another component) would point at absent nodes.
  useEffect(() => {
    useValidationStore.getState().setIssues([]);
  }, [scopeKey]);

  useEffect(() => {
    if (!loaded || !catalogReady) return undefined;
    let cancelled = false;
    useValidationStore.getState().setPending(true);
    const timer = setTimeout(async () => {
      try {
        const graph = useGraphStore.getState().graph;
        // Inside a component the definition is checked (ports, parameters; no source/sink rules).
        const session = useComponentStore.getState().sessions.at(-1);
        const issues = session
          ? await api.validateComponent(draftDefinition(session, graph))
          : await api.validate(graph);
        if (!cancelled) useValidationStore.getState().setIssues(issues);
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof ApiError && error.status === 503 ? null : errorMessage(error);
        useValidationStore.getState().setError(message);
      }
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [revision, loaded, catalogReady, session]);
}
