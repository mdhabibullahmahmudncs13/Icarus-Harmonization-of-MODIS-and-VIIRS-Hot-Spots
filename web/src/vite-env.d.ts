/// <reference types="vite/client" />

/** Data source selection: "mock" (default) or "api". */
interface ImportMetaEnv {
  readonly VITE_DATA?: "mock" | "api";
  /**
   * Origin the `/api` requests are sent to. Empty (the default) keeps them on
   * the app's own origin, which is what the dev and preview proxies expect.
   */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
