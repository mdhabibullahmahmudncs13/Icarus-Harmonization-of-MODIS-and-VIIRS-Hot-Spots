/* Icarus service worker — docs/IMPLEMENTATION_PLAN.md §7 (offline hardening).
 *
 * Hand-rolled rather than Workbox: two shells (the app and the landing page),
 * a handful of JSON payloads and hashed assets, so the whole worker is smaller
 * than its config would be. Same-origin only — a third-party request is never
 * fetched here, let alone cached.
 *
 * Strategy:
 *   navigations   network-first, cached shell as the offline fallback
 *   /mock/, /api/ stale-while-revalidate (instant from cache, fresh behind)
 *   everything else (hashed assets) cache-first
 *
 * Caches are versioned (`icarus-<part>-v<N>`); an activate of a new worker
 * deletes every icarus cache it does not own.
 */
const VERSION = 'v1';
const SHELL_CACHE = `icarus-shell-${VERSION}`;
const DATA_CACHE = `icarus-data-${VERSION}`;
// Every navigable document, so either one cold-starts offline.
const PRECACHE = ['/', '/index.html', '/landing.html'];

// Cache API lookups that must not fail on transport metadata:
// the preview server answers with `Vary: Origin` and (for compressed
// responses) a `content-encoding` header whose body the Cache API already
// holds decoded. Storing a normalized copy and matching with `ignoreVary`
// is what makes a cached script actually load offline instead of failing
// with net::ERR_FAILED.
const MATCH_OPTIONS = { ignoreVary: true };

async function putNormalized(cache, key, response) {
  if (!response || !response.ok) return;
  const headers = new Headers(response.headers);
  headers.delete('content-encoding');
  headers.delete('content-length');
  headers.delete('vary');
  const body = await response.clone().arrayBuffer();
  await cache.put(key, new Response(body, { status: response.status, statusText: response.statusText, headers }));
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then(async (cache) => {
        for (const url of PRECACHE) {
          await putNormalized(cache, url, await fetch(url));
        }
      })
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith('icarus-') && !key.endsWith(`-${VERSION}`))
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

// The page reports the resources it actually used (hashed assets, data
// payloads) once the worker controls it — they were fetched before this
// worker existed, so no fetch event ever saw them. Without this the offline
// reload would find an empty asset cache.
self.addEventListener('message', (event) => {
  const data = event.data;
  if (!data || data.type !== 'icarus:precache' || !Array.isArray(data.urls)) return;
  const sameOrigin = data.urls.filter((value) => {
    if (typeof value !== 'string') return false;
    try {
      return new URL(value, self.location.origin).origin === self.location.origin;
    } catch {
      return false;
    }
  });
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) =>
        Promise.all(
          sameOrigin.map((url) =>
            fetch(url)
              .then((response) => putNormalized(cache, url, response))
              .catch(() => undefined),
          ),
        ),
      ),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  // Foreign origin: let the browser handle it normally. The worker never
  // fetches or caches anything that is not the preview server itself.
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    // Online stays current; the precached shell is what makes a cold start
    // with the network off succeed. Keyed by the page's own path: there are two
    // navigable documents, and filing both under `/index.html` would let a
    // landing visit overwrite the app shell (and serve the app offline).
    const key = url.pathname;
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          void caches.open(SHELL_CACHE).then((cache) => putNormalized(cache, key, copy));
          return response;
        })
        .catch(() =>
          caches
            .match(key, MATCH_OPTIONS)
            .then((cached) => cached || caches.match('/', MATCH_OPTIONS)),
        ),
    );
    return;
  }

  if (url.pathname.startsWith('/mock/') || url.pathname.startsWith('/api/')) {
    // Stale-while-revalidate, looked up across every cache: the page's
    // precache report puts payloads in the shell cache, freshly fetched
    // ones land here.
    event.respondWith(
      caches.open(DATA_CACHE).then(async (own) => {
        const cached = await caches.match(request, MATCH_OPTIONS);
        const network = fetch(request)
          .then((response) => {
            if (response && response.ok) void putNormalized(own, request, response.clone());
            return response;
          })
          .catch(() => undefined);
        if (cached) return cached;
        const response = await network;
        return response || Response.error();
      }),
    );
    return;
  }

  // Hashed, immutable assets: cache-first, across every cache.
  event.respondWith(
    caches.open(SHELL_CACHE).then(async (own) => {
      const cached = await caches.match(request, MATCH_OPTIONS);
      if (cached) return cached;
      const response = await fetch(request);
      if (response && response.ok) void putNormalized(own, request, response.clone());
      return response;
    }),
  );
});
