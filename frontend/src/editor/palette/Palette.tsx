import { useMemo, useRef, useState } from "react";
import type { ElementSummary, Family } from "../../api/types";
import { Icon } from "../../components/Icon";
import { groupElements, loadExpanded, saveExpanded, type GroupId } from "../../lib/paletteGroups";
import { COMMON_ELEMENTS, EMPTY_FILTERS, searchElements, type PaletteFilters } from "../../lib/search";
import { useCatalogStore } from "../../store/catalogStore";
import { FilterChips } from "./FilterChips";
import { PaletteGroupSection } from "./PaletteGroupSection";
import { PaletteItem } from "./PaletteItem";
import { useAddElement } from "./useAddElement";
import { ComponentNameDialog } from "../blocks/ComponentNameDialog";
import { createComponent, importComponentFile } from "../blocks/componentActions";
import { StartersDialog } from "../blocks/StartersDialog";
import { ADVANCED } from "../../lib/features";

export function Palette() {
  const elements = useCatalogStore((state) => state.elements);
  const byName = useCatalogStore((state) => state.byName);
  const catalogState = useCatalogStore((state) => state.state);
  const [filters, setFilters] = useState<PaletteFilters>(EMPTY_FILTERS);
  const [showFilters, setShowFilters] = useState(false);
  const [expanded, setExpanded] = useState<GroupId[]>(loadExpanded);
  const addElement = useAddElement();
  const [creating, setCreating] = useState(false);
  const [showStarters, setShowStarters] = useState(false);
  const importInput = useRef<HTMLInputElement>(null);

  const filtering = filters.query.trim() !== "" || filters.categories.length > 0 || filters.families.length > 0;
  const results = useMemo(() => (filtering ? searchElements(elements, filters) : elements), [elements, filters, filtering]);
  const groups = useMemo(() => groupElements(results), [results]);
  const common = useMemo(
    () => COMMON_ELEMENTS.map((name) => byName[name]).filter((e): e is ElementSummary => e !== undefined),
    [byName],
  );

  const update = (patch: Partial<PaletteFilters>) => setFilters((current) => ({ ...current, ...patch }));
  const toggle = <T extends string>(list: T[], value: T) =>
    list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
  const toggleGroup = (id: GroupId) => {
    const next = toggle(expanded, id);
    setExpanded(next);
    saveExpanded(next);
  };

  return (
    <aside className="palette">
      <div className="palette-search">
        <Icon name="search" className="faint" />
        <input
          className="input"
          placeholder={`Search ${elements.length || ""} elements…`}
          value={filters.query}
          onChange={(event) => update({ query: event.target.value })}
          aria-label="Search elements"
        />
        <button className={`icon-btn${showFilters || filtering ? " active" : ""}`} title="Filters"
          onClick={() => setShowFilters(!showFilters)} aria-label="Toggle filters">
          <Icon name="chevronDown" />
        </button>
      </div>
      {showFilters ? (
        <FilterChips
          filters={filters}
          onCategory={(category) => update({ categories: toggle(filters.categories, category) })}
          onFamily={(family: Family) => update({ families: toggle(filters.families, family) })}
          onClear={() => update({ categories: [], families: [] })}
        />
      ) : null}
      <div className="palette-list">
        {catalogState !== "ready" ? (
          <div className="empty-state">
            <span className="spinner" /> <div>Loading the element catalog…</div>
          </div>
        ) : null}
        {!filtering && common.length > 0 ? (
          <>
            <div className="palette-section">Common</div>
            {common.map((element) => (
              <PaletteItem key={`common-${element.name}`} element={element} onAdd={addElement} />
            ))}
            <div className="palette-section">By category</div>
          </>
        ) : null}
        {filtering ? <div className="palette-section">{results.length} matches</div> : null}
        {!filtering ? (
          <div className="palette-actions">
            <button className="btn btn-sm" onClick={() => setCreating(true)}
              title="A reusable macro block in the library">
              <Icon name="plus" size={12} /> New component
            </button>
            <button className="btn btn-sm" onClick={() => setShowStarters(true)}
              title="Ready-made components: RTSP inputs, encoders, recorders, network outputs">
              Starters…
            </button>
            <button className="btn btn-sm" onClick={() => importInput.current?.click()} title="Add components from a file">
              <Icon name="import" size={12} /> Import…
            </button>
            <input ref={importInput} type="file" accept=".json,application/json" hidden aria-label="Component file"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void importComponentFile(file);
              }} />
          </div>
        ) : null}
        {groups.map((group) => (
          <PaletteGroupSection
            key={group.id}
            group={group}
            expanded={filtering || expanded.includes(group.id)}
            onToggle={() => toggleGroup(group.id)}
            onAdd={addElement}
          />
        ))}
        {filtering && results.length === 0 ? <div className="empty-state">No element matches.</div> : null}
      </div>
      <div className="palette-hint faint">
        Drag onto the canvas or double-click to add{ADVANCED ? " · Alt-drag a component for a slot" : ""}
      </div>
      {creating ? (
        <ComponentNameDialog title="New component" confirmLabel="Create and open"
          hint="An empty component opens on the canvas: add elements, expose ports and parameters, then save it."
          onSubmit={createComponent} onClose={() => setCreating(false)} />
      ) : null}
      {showStarters ? <StartersDialog onClose={() => setShowStarters(false)} /> : null}
    </aside>
  );
}
