import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Self-hosted fonts, bundled locally — no CDN, no remote fonts (DESIGN.md §4.5).
import "@fontsource-variable/fraunces";
import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/700.css";

import "./styles/tokens.css";
import "./styles/app.css";
import App from "./App";

const root = document.getElementById("root");
if (root === null) throw new Error("missing #root element");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
