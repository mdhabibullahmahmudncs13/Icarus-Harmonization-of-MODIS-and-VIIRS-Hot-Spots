import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

// Self-hosted fonts, bundled locally — no CDN, no remote fonts (plan, principle 5).
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/600.css";

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
