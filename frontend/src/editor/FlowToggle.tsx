import { Icon } from "../components/Icon";
import { prefersReducedMotion } from "../lib/motion";
import { useUiStore } from "../store/uiStore";

/** Switches the "buffer flow" dots travelling along links on and off. */
export function FlowToggle() {
  const enabled = useUiStore((state) => state.flowAnimation);
  const setEnabled = useUiStore((state) => state.setFlowAnimation);
  const reduced = prefersReducedMotion();
  const title = reduced
    ? "Buffer flow animation is off because the system asks for reduced motion"
    : `${enabled ? "Hide" : "Show"} buffers travelling along the links`;
  return (
    <button className={`icon-btn${enabled && !reduced ? " active" : ""}`} onClick={() => setEnabled(!enabled)}
      disabled={reduced} aria-pressed={enabled && !reduced} aria-label="Buffer flow animation" title={title}>
      <Icon name="flow" />
    </button>
  );
}
