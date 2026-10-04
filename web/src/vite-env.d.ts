/// <reference types="vite/client" />

/** Data source selection: "mock" (default) or "api". */
interface ImportMetaEnv {
  readonly VITE_DATA?: "mock" | "api";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
