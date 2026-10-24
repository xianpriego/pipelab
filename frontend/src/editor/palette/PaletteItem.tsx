import { memo, type DragEvent } from "react";
import type { ElementSummary } from "../../api/types";
import { accentColor } from "../../lib/elementKinds";

export const ELEMENT_MIME = "application/x-pipelab-element";

interface PaletteItemProps {
  element: ElementSummary;
  onAdd: (factory: string) => void;
}

function tooltip(element: ElementSummary): string {
  return [element.long_name, element.klass, element.description, `plugin: ${element.plugin} (${element.family})`]
    .filter(Boolean)
    .join("\n");
}

export const PaletteItem = memo(function PaletteItem({ element, onAdd }: PaletteItemProps) {
  const onDragStart = (event: DragEvent) => {
    event.dataTransfer.setData(ELEMENT_MIME, element.name);
    event.dataTransfer.setData("text/plain", element.name);
    event.dataTransfer.effectAllowed = "copy";
  };
  return (
    <div
      className="palette-item"
      draggable
      onDragStart={onDragStart}
      onDoubleClick={() => onAdd(element.name)}
      title={tooltip(element)}
      style={{ borderLeftColor: accentColor(element) }}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => event.key === "Enter" && onAdd(element.name)}
    >
      <div className="palette-item-top">
        <span className="palette-item-name">{element.name}</span>
        {element.categories.includes("hardware") ? (
          <span className="gpu-badge" title="Runs on a GPU or dedicated hardware">GPU</span>
        ) : null}
        <span className={`family-badge family-${element.family}`}>{element.family}</span>
      </div>
      <div className="palette-item-desc">{element.long_name || element.klass}</div>
    </div>
  );
});
