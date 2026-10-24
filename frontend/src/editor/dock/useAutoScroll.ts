import { useEffect, useRef } from "react";

/** Keeps a scroll container pinned to the bottom while ``enabled``. */
export function useAutoScroll<T extends HTMLElement>(dependency: unknown, enabled: boolean) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (enabled && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [dependency, enabled]);
  return ref;
}
