import { defineConfig } from 'vite';

/**
 * The landing page is a separate, self-contained site: the pitch, and a button
 * through to the live app on its own dev server (`web/`, port 5174).
 *
 * Keep it offline-first like the app: `three` is bundled and every texture is
 * served from `public/earth/`, so the page makes no third-party request — the
 * same property `web/e2e/no-third-party.spec.ts` guards for the app.
 */
export default defineConfig({
  server: { port: 5175, strictPort: true },
  preview: { port: 4175, strictPort: true },
  build: { target: 'es2022' },
});
