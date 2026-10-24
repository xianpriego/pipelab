import { useState, type ReactNode } from "react";
import { Icon } from "../../components/Icon";

interface CollapsibleProps {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function Collapsible({ title, defaultOpen = false, children }: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="inspector-section collapsible">
      <button className="collapsible-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Icon name={open ? "chevronDown" : "chevronUp"} size={12} />
        <h3>{title}</h3>
      </button>
      {open ? <div className="collapsible-body">{children}</div> : null}
    </section>
  );
}
