import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { ProjectSummary } from "../api/types";
import { Icon } from "../components/Icon";
import { ThemeToggle } from "../components/ThemeToggle";
import { CatalogBanner } from "../projects/CatalogBanner";
import { ImportProjectDialog } from "../projects/ImportProjectDialog";
import { NewProjectDialog } from "../projects/NewProjectDialog";
import { ProjectCard } from "../projects/ProjectCard";
import { notify } from "../store/uiStore";

type OpenDialog = "new" | "import" | null;

export function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [dialog, setDialog] = useState<OpenDialog>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listProjects();
      setProjects([...list].sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
    } catch (error) {
      setProjects([]);
      notify({ level: "error", title: "Could not load pipelines", message: errorMessage(error) });
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const duplicate = async (project: ProjectSummary) => {
    try {
      await api.duplicateProject(project.id);
      await refresh();
    } catch (error) {
      notify({ level: "error", title: "Duplicate failed", message: errorMessage(error) });
    }
  };

  const remove = async (project: ProjectSummary) => {
    if (!window.confirm(`Delete "${project.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteProject(project.id);
      await refresh();
    } catch (error) {
      notify({ level: "error", title: "Delete failed", message: errorMessage(error) });
    }
  };

  return (
    <div className="projects-page">
      <header className="projects-header">
        <img src="/favicon.svg" alt="" width={30} height={30} />
        <div>
          <h1>Pipelab</h1>
          <div className="muted">Prototype GStreamer pipelines visually, run them and export the skeleton.</div>
        </div>
        <span className="spacer" />
        <button className="btn" onClick={() => navigate("/monitor")} title="Inspect pipelines running live on this machine">
          <Icon name="eye" /> Live monitor
        </button>
        <button className="btn" onClick={() => setDialog("import")}>
          <Icon name="import" /> Import
        </button>
        <button className="btn btn-primary" onClick={() => setDialog("new")}>
          <Icon name="plus" /> New pipeline
        </button>
        <ThemeToggle />
      </header>
      <main className="projects-main">
        <CatalogBanner />
        {projects === null ? (
          <div className="empty-state">
            <span className="spinner" />
          </div>
        ) : projects.length === 0 ? (
          <div className="empty-state projects-empty">
            <h3>No pipelines yet</h3>
            <p>Create a workspace from scratch or a starter template, or import a gst-launch line.</p>
            <button className="btn btn-primary" onClick={() => setDialog("new")}>
              <Icon name="plus" /> New pipeline
            </button>
          </div>
        ) : (
          <div className="project-grid">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onOpen={() => navigate(`/projects/${project.id}`)}
                onDuplicate={() => void duplicate(project)}
                onDelete={() => void remove(project)}
              />
            ))}
          </div>
        )}
      </main>
      {dialog === "new" ? (
        <NewProjectDialog onClose={() => setDialog(null)} onCreated={(id) => navigate(`/projects/${id}`)} />
      ) : null}
      {dialog === "import" ? (
        <ImportProjectDialog onClose={() => setDialog(null)} onCreated={(id) => navigate(`/projects/${id}`)} />
      ) : null}
    </div>
  );
}
