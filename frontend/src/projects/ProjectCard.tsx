import type { ProjectSummary } from "../api/types";
import { Icon } from "../components/Icon";
import { formatDate } from "../lib/format";

interface ProjectCardProps {
  project: ProjectSummary;
  onOpen: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

export function ProjectCard({ project, onOpen, onDuplicate, onDelete }: ProjectCardProps) {
  return (
    <article className="project-card" onClick={onOpen} onKeyDown={(e) => e.key === "Enter" && onOpen()} tabIndex={0}>
      <div className="project-card-preview" aria-hidden>
        <Icon name="graph" size={28} />
      </div>
      <div className="project-card-body">
        <h3 title={project.name}>{project.name}</h3>
        <p className="muted">{project.description || "No description"}</p>
        <div className="row faint">
          <span>{project.node_count} elements</span>
          <span>·</span>
          <span>{formatDate(project.updated_at)}</span>
        </div>
      </div>
      <div className="project-card-actions" onClick={(event) => event.stopPropagation()}>
        <button className="icon-btn" title="Duplicate" aria-label="Duplicate" onClick={onDuplicate}>
          <Icon name="copy" />
        </button>
        <button className="icon-btn" title="Delete" aria-label="Delete" onClick={onDelete}>
          <Icon name="trash" />
        </button>
      </div>
    </article>
  );
}
