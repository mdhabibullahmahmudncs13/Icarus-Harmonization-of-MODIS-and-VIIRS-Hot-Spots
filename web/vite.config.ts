import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Offline-first: the build must not reference any external host.
export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
  build: { target: 'es2022' },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    globals: true,
  },
});
