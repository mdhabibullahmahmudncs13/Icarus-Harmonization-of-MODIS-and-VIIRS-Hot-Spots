/**
 * Register the offline service worker (`docs/IMPLEMENTATION_PLAN.md` §7) and
 * tell it which resources this page needs.
 *
 * Production builds only: during development the dev server owns the module
 * graph and a worker would keep serving stale bundles. Registration failure
 * must never take the app down — the online experience is unchanged without
 * the worker; only the offline cold start (the §7 gate) needs it.
 *
 * Two things are reported to the worker:
 *
 * 1. The nine mock payloads, listed explicitly. Their fetches race the worker's
 *    activation on a first visit, so a fetch event may never see them; the
 *    worker fetches them itself when it gets the report, which makes the
 *    offline cold start deterministic instead of timing-dependent.
 * 2. The performance timeline — the hashed assets, which are always loaded
 *    before the worker activates and so are never caught by a fetch event.
 *
 * The report is idempotent (a cache put overwrites), so sending it again once
 * things settle only picks up stragglers, e.g. the slower payloads of an
 * API-backed build.
 */
const MOCK_PAYLOADS = [
  'meta.json',
  'series.json',
  'cells.json',
  'baseline.json',
  'anomaly.json',
  'critical-period.json',
  'validation.json',
  'methods.json',
  'aoi.json',
] as const;

export function registerServiceWorker(): void {
  if (!import.meta.env.PROD) return;
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) return;

  const reportUsedResources = () => {
    const urls = new Set<string>([window.location.href, '/index.html']);
    if ((import.meta.env.VITE_DATA ?? 'mock') !== 'api') {
      for (const name of MOCK_PAYLOADS) urls.add(`/mock/${name}`);
    }
    for (const entry of performance.getEntriesByType('resource')) {
      urls.add(entry.name);
    }
    const sameOrigin = [...urls].filter((value) => {
      try {
        return new URL(value, window.location.origin).origin === window.location.origin;
      } catch {
        return false;
      }
    });
    navigator.serviceWorker.controller?.postMessage({
      type: 'icarus:precache',
      urls: sameOrigin,
    });
  };

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then(() => {
        const onceControlled = () => {
          reportUsedResources();
          // Idempotent second pass for payloads that were still in flight
          // when the worker took control.
          window.setTimeout(reportUsedResources, 2000);
        };
        if (navigator.serviceWorker.controller) {
          onceControlled();
        } else {
          navigator.serviceWorker.addEventListener('controllerchange', onceControlled, {
            once: true,
          });
        }
      })
      .catch((error: unknown) => {
        console.warn('service worker registration failed; online behaviour is unchanged', error);
      });
  });
}
