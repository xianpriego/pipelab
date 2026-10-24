import type { Family } from "../../api/types";
import { CATEGORY_FILTERS, FAMILY_FILTERS, type PaletteFilters } from "../../lib/search";

interface FilterChipsProps {
  filters: PaletteFilters;
  onCategory: (category: string) => void;
  onFamily: (family: Family) => void;
  onClear: () => void;
}

const FAMILY_LABELS: Partial<Record<Family, string>> = { rs: "rust", libav: "libav/ffmpeg" };

export function FilterChips({ filters, onCategory, onFamily, onClear }: FilterChipsProps) {
  return (
    <div className="palette-filters">
      <div className="chip-row">
        {CATEGORY_FILTERS.map((category) => (
          <button key={category} className={`chip${filters.categories.includes(category) ? " on" : ""}`}
            onClick={() => onCategory(category)}>
            {category}
          </button>
        ))}
      </div>
      <div className="chip-row">
        {FAMILY_FILTERS.map((family) => (
          <button key={family} className={`chip${filters.families.includes(family) ? " on" : ""}`}
            onClick={() => onFamily(family)}>
            {FAMILY_LABELS[family] ?? family}
          </button>
        ))}
        {filters.categories.length + filters.families.length > 0 ? (
          <button className="chip" onClick={onClear}>clear</button>
        ) : null}
      </div>
    </div>
  );
}
