import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

import { assertReleaseDataSource } from './src/lib/source';

/**
 * Offline-first: the build must not reference any external host.
 *
 * Release guard (`docs/IMPLEMENTATION_PLAN.md` §3.3): a release build must not
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
    plugins: [react()],
    server: { port: 5174 },
    build: { target: 'es2022' },
    test: {
      environment: 'node',
      include: ['tests/**/*.test.ts'],
      globals: true,
    },
  };
});
