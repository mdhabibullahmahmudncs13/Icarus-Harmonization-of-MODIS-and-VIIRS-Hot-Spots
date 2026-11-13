import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { serviceWorkerFingerprint } from '../vite.config';

const WORKER = readFileSync(fileURLToPath(new URL('../public/sw.js', import.meta.url)), 'utf8');

describe('serviceWorkerFingerprint', () => {
  it('changes when the build changes', () => {
    // The regression this guards: the worker's version was the literal 'v1',
    // so a browser never installed the new worker after a deploy and kept
    // serving the old caches.
    const before = serviceWorkerFingerprint(['main-aaa.js'], '<html></html>');
    const after = serviceWorkerFingerprint(['main-bbb.js'], '<html></html>');
    expect(before).not.toBe(after);
  });

  it('changes when the shell changes', () => {
    expect(serviceWorkerFingerprint(['main-aaa.js'], '<html>a</html>')).not.toBe(
      serviceWorkerFingerprint(['main-aaa.js'], '<html>b</html>'),
    );
  });

  it('is the same for the same build', () => {
    expect(serviceWorkerFingerprint(['main-aaa.js'], '<html></html>')).toBe(
      serviceWorkerFingerprint(['main-aaa.js'], '<html></html>'),
    );
  });
});

describe('the service worker source', () => {
  it('names its caches by the version the build stamps in', () => {
    // The stamp replaces this literal, so it has to be there and it has to be
    // the only version the worker uses.
    expect(WORKER).toContain("const VERSION = 'v1'");
    expect(WORKER).toContain('icarus-shell-${VERSION}');
    expect(WORKER).toContain('icarus-data-${VERSION}');
  });
});
