import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Vite config for the Icarus frontend.
// Offline by design: no CDN, no remote fonts, no third-party requests.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // The repository path contains a colon ("Icarus: Harmonization…"), and
    // Vite's fs allow check rejects any file path containing ":" (it only
    // strips Windows drive letters), which 403s the app's own files.
    // Disable the strict allow-list for this loopback-only dev server;
    // it is bound to 127.0.0.1 and serves no other directory on purpose.
    fs: { strict: false },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    include: ["tests/unit/**/*.test.ts"],
    globals: false,
  },
});
