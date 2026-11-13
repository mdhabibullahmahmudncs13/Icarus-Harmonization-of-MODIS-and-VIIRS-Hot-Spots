import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig, type Plugin } from 'vitest/config';

import { assertReleaseDataSource } from './src/lib/source';

/**
 * The fingerprint the service worker is stamped with.
 *
 * It is taken from what the build emitted — the hashed asset names and the
 * shell — so it changes exactly when the app changes, and stays the same
 * when it does not.
 */
export function serviceWorkerFingerprint(assets: string[], shell: string): string {
  return createHash('sha256').update(assets.join('\n')).update(shell).digest('hex').slice(0, 12);
}

/**
 * Stamp the service worker with the build's own fingerprint.
 *
 * A browser installs a new service worker only when the script's bytes
 * change. `VERSION = 'v1'` never changes, so after a deploy the old worker
 * stays installed, it keeps the old caches, and the new hashed assets are
 * never cached: the app works online and breaks offline, and the panels can
 * show last week's series next to this week's cells.
 */
function serviceWorkerVersion(): Plugin {
  let outDir = '';
  return {
    name: 'icarus:service-worker-version',
    apply: 'build',
    configResolved(config) {
      // Absolute, and resolved against the config root rather than the working
      // directory: the build runs from `web/`, and a path relative to the cwd
      // would point at the wrong directory.
      outDir = resolve(config.root, config.build.outDir);
    },
    closeBundle() {
      const worker = join(outDir, 'sw.js');
      const assets = join(outDir, 'assets');
      const names = statSync(assets).isDirectory() ? readdirSync(assets).sort() : [];
      const fingerprint = serviceWorkerFingerprint(
        names,
        readFileSync(join(outDir, 'index.html'), 'utf8'),
      );
      writeFileSync(
        worker,
        readFileSync(worker, 'utf8').replace(
          /const VERSION = '[^']*'/,
          `const VERSION = 'v${fingerprint}'`,
        ),
      );
    },
  };
}

/**
 * Offline-first: the build must not reference any external host.
 *
 * Release guard (docs/IMPLEMENTATION_PLAN.md §3.3): a release build must not
 * ship on data that is not evidence, so `vite build --mode release` fails when
 * `VITE_DATA` is not `api`. An ordinary `vite build` is unaffected and still
 * produces the mock preview the interface work needs.
 */
export default defineConfig(({ command, mode }) => {
  // ``loadEnv`` merges .env files with the prefixed process-environment
  // entries, which is the same value ``import.meta.env.VITE_DATA`` will see.
  const env = loadEnv(mode, '.', 'VITE_');
  const dataMode = env.VITE_DATA ?? 'mock';
  if (command === 'build') {
    assertReleaseDataSource(dataMode, mode === 'release');
  }

  return {
    plugins: [react(), serviceWorkerVersion()],
    server: { port: 5174 },
    build: {
      target: 'es2022',
      // Two entries, one build: the app at `/` and the landing page at
      // `/landing.html`.
      rollupOptions: { input: { main: 'index.html', landing: 'landing.html' } },
    },
    test: {
      environment: 'node',
      include: ['tests/**/*.test.ts'],
      globals: true,
    },
  };
});
