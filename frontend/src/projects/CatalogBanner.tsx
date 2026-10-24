import { useCatalogStore } from "../store/catalogStore";

export function CatalogBanner() {
  const state = useCatalogStore((s) => s.state);
  const health = useCatalogStore((s) => s.health);
  const error = useCatalogStore((s) => s.error);

  // Downloading an already built catalog is quick: only announce real server-side builds.
  if (state === "building") {
    const done = health?.catalog.done ?? 0;
    const total = health?.catalog.total ?? 0;
    const percent = total > 0 ? Math.round((done / total) * 100) : 0;
    return (
      <div className="catalog-banner" role="status">
        <span className="spinner" />
        <div className="spacer">
          <strong>Building the GStreamer element catalog…</strong>
          <div className="muted">
            Every installed element is introspected once per machine{total > 0 ? ` (${done} / ${total})` : ""}.
          </div>
          <div className="progress">
            <div style={{ width: `${percent}%` }} />
          </div>
        </div>
      </div>
    );
  }
  if (state === "error") {
    return (
      <div className="catalog-banner error" role="alert">
        <strong>The element catalog could not be loaded.</strong>
        <span className="muted">{error}</span>
      </div>
    );
  }
  return null;
}
