import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/overlays.css";
import "./styles/projects.css";
import "./styles/editor.css";
import "./styles/canvas.css";
import "./styles/palette.css";
import "./styles/inspector.css";
import "./styles/dock.css";
import "./styles/components.css";
import "./styles/perf.css";
import { App } from "./App";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
