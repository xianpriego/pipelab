import { useEffect } from "react";
import type { ElementInfo } from "../api/types";
import { useCatalogStore } from "../store/catalogStore";

/** Full element description (properties, templates), loaded on demand and cached. */
export function useElementDetails(factory: string | undefined): ElementInfo | undefined {
  const details = useCatalogStore((state) => (factory ? state.details[factory] : undefined));
  const ready = useCatalogStore((state) => state.state === "ready");
  const known = useCatalogStore((state) => (factory ? factory in state.byName : false));
  useEffect(() => {
    if (factory && ready && known && !details) void useCatalogStore.getState().loadDetails(factory);
  }, [factory, ready, known, details]);
  return details;
}
