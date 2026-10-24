import type { Connection } from "@xyflow/react";
import { useCallback } from "react";
import { api, errorMessage } from "../../api/client";
import type { GraphEdge } from "../../api/types";
import { newId } from "../../lib/ids";
import { useGraphStore } from "../../store/graphStore";
import { notify } from "../../store/uiStore";
import { reportLinkResult } from "../actions";

/** Asks the backend whether a link is valid before adding it to the graph. */
export function useConnect(): (connection: Connection) => void {
  return useCallback((connection: Connection) => {
    if (!connection.sourceHandle || !connection.targetHandle) return;
    const edge: GraphEdge = {
      id: newId("e"),
      source: connection.source,
      source_pad: connection.sourceHandle,
      target: connection.target,
      target_pad: connection.targetHandle,
    };
    const graph = useGraphStore.getState().graph;
    api
      .checkLink(graph, edge)
      .then((result) => {
        if (result.allowed) useGraphStore.getState().addEdge(result.edge);
        reportLinkResult(result);
      })
      .catch((error) => notify({ level: "error", title: "Link check failed", message: errorMessage(error) }));
  }, []);
}
