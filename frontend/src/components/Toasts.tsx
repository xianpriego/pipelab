import { useEffect } from "react";
import { useUiStore, type Toast } from "../store/uiStore";
import { Icon } from "./Icon";

const DEFAULT_TIMEOUT: Record<Toast["level"], number> = { info: 5000, success: 3500, warning: 9000, error: 0 };
const ICONS = { info: "info", success: "check", warning: "warning", error: "error" } as const;

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useUiStore((state) => state.dismiss);
  const timeout = toast.timeout ?? (toast.actions?.length ? 0 : DEFAULT_TIMEOUT[toast.level]);

  useEffect(() => {
    if (!timeout) return undefined;
    const timer = setTimeout(() => dismiss(toast.id), timeout);
    return () => clearTimeout(timer);
  }, [dismiss, timeout, toast.id]);

  return (
    <div className={`toast ${toast.level}`} role={toast.level === "error" ? "alert" : "status"}>
      <div className="toast-title">
        <Icon name={ICONS[toast.level]} />
        <span className="spacer">{toast.title}</span>
        <button className="icon-btn" style={{ width: 20, height: 20 }} onClick={() => dismiss(toast.id)} aria-label="Dismiss">
          <Icon name="close" size={12} />
        </button>
      </div>
      {toast.message ? <div className="toast-message">{toast.message}</div> : null}
      {toast.details?.length ? (
        <ul>
          {toast.details.map((detail) => (
            <li key={detail}>{detail}</li>
          ))}
        </ul>
      ) : null}
      {toast.actions?.length ? (
        <div className="toast-actions">
          {toast.actions.map((action) => (
            <button
              key={action.label}
              className="btn btn-sm btn-primary"
              onClick={() => {
                dismiss(toast.id);
                action.run();
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function Toasts() {
  const toasts = useUiStore((state) => state.toasts);
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
