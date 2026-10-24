import { Icon } from "../components/Icon";
import { useUiStore } from "../store/uiStore";
import { useValidationStore } from "../store/validationStore";

export function ValidationBadge() {
  const counts = useValidationStore((state) => state.counts);
  const pending = useValidationStore((state) => state.pending);
  const setDockTab = useUiStore((state) => state.setDockTab);
  const clean = counts.error + counts.warning + counts.info === 0;
  return (
    <button className="validation-badge" onClick={() => setDockTab("issues")} title="Show validation issues">
      {pending ? <span className="spinner" /> : null}
      {clean && !pending ? (
        <span className="badge success"><Icon name="check" size={12} /> Valid</span>
      ) : null}
      {counts.error > 0 ? <span className="badge error"><Icon name="error" size={12} /> {counts.error}</span> : null}
      {counts.warning > 0 ? <span className="badge warning"><Icon name="warning" size={12} /> {counts.warning}</span> : null}
      {counts.info > 0 ? <span className="badge info"><Icon name="info" size={12} /> {counts.info}</span> : null}
    </button>
  );
}
