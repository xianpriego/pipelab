import { memo, useState, type CSSProperties } from "react";
import { Icon } from "../../components/Icon";
import { GROUP_ACCENTS, type PaletteGroup } from "../../lib/paletteGroups";
import { PaletteItem } from "./PaletteItem";

const PAGE = 100;

interface PaletteGroupSectionProps {
  group: PaletteGroup;
  expanded: boolean;
  onToggle: () => void;
  onAdd: (factory: string) => void;
}

export const PaletteGroupSection = memo(function PaletteGroupSection({
  group, expanded, onToggle, onAdd,
}: PaletteGroupSectionProps) {
  const [limit, setLimit] = useState(PAGE);
  return (
    <section className={`palette-group group-${group.id}`} style={{ "--group-accent": GROUP_ACCENTS[group.id] } as CSSProperties}>
      <button type="button" className="palette-group-header" aria-expanded={expanded} onClick={onToggle}>
        <Icon name={expanded ? "chevronDown" : "chevronRight"} size={12} />
        <span className="palette-group-dot" />
        <span className="palette-group-label">{group.label}</span>
        <span className="palette-group-count">{group.elements.length}</span>
      </button>
      {expanded ? (
        <div className="palette-group-items">
          {group.elements.slice(0, limit).map((element) => (
            <PaletteItem key={element.name} element={element} onAdd={onAdd} />
          ))}
          {group.elements.length > limit ? (
            <button className="btn btn-ghost palette-more" onClick={() => setLimit(limit + PAGE)}>
              Show more ({group.elements.length - limit} left)
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
});
