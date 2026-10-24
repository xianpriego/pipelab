import { Fragment, useMemo } from "react";
import { Icon } from "../../components/Icon";
import { isDirty, useComponentStore } from "../../store/componentStore";
import { useGraphStore } from "../../store/graphStore";
import { useProjectStore } from "../../store/projectStore";
import { discardComponent, leaveTo, saveComponent } from "./componentActions";

/** Breadcrumbs while a component definition is open: Project › rtsp-input › …, with Save/Discard. */
export function ScopeBar() {
  const sessions = useComponentStore((state) => state.sessions);
  const graph = useGraphStore((state) => state.graph);
  const projectName = useProjectStore((state) => state.meta?.name ?? "Project");
  const current = sessions[sessions.length - 1];
  const dirty = useMemo(() => (current ? isDirty(current, graph) : false), [current, graph]);
  if (!current) return null;

  return (
    <div className="scope-bar" role="navigation" aria-label="Component breadcrumbs">
      <div className="row scope-crumbs">
        <Icon name="graph" size={13} />
        <button className="link-btn" onClick={() => leaveTo(0)} title="Back to the project">{projectName}</button>
        {sessions.map((session, index) => (
          <Fragment key={`${session.base.id}-${index}`}>
            <span className="faint" aria-hidden>›</span>
            {index === sessions.length - 1 ? (
              <strong aria-current="page">{session.name}</strong>
            ) : (
              <button className="link-btn" onClick={() => leaveTo(index + 1)}>{session.name}</button>
            )}
          </Fragment>
        ))}
        {current.path.length === 0 ? <span className="badge" title="Opened from the library: no runtime data">library</span> : null}
        {dirty ? <span className="badge warning">unsaved</span> : null}
        <span className="spacer" />
        <button className="btn btn-sm" onClick={discardComponent} disabled={!dirty}>Discard</button>
        <button className="btn btn-sm btn-primary" onClick={() => void saveComponent()} disabled={!dirty}
          title="Saves the definition in the library">
          <Icon name="save" size={12} /> Save component
        </button>
        <button className="icon-btn" aria-label="Close the component" title="Back one level"
          onClick={() => leaveTo(sessions.length - 1)}>
          <Icon name="close" size={13} />
        </button>
      </div>
      <div className="scope-warning">
        Editing the library definition of <strong>{current.name}</strong> (component:{current.base.id}, v{current.base.version}):
        saving changes it in every project that uses it.
      </div>
    </div>
  );
}
