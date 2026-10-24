import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toasts } from "./components/Toasts";
import { EditorPage } from "./pages/EditorPage";
import { MonitorPage } from "./pages/MonitorPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { useCatalogStore } from "./store/catalogStore";
import { useUiStore } from "./store/uiStore";

export function App() {
  const theme = useUiStore((state) => state.theme);
  const loadCatalog = useCatalogStore((state) => state.load);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/projects/:id" element={<EditorPage />} />
        <Route path="/monitor" element={<MonitorPage />} />
        <Route path="*" element={<ProjectsPage />} />
      </Routes>
      <Toasts />
    </BrowserRouter>
  );
}
