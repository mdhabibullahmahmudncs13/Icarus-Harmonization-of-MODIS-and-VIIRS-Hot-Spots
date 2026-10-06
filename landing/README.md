# Icarus landing page

The pitch page: what Icarus is, how the pipeline works, and a button through to
the live app on **<http://localhost:5174/>**.

It is a separate, self-contained site from `web/` (which *is* the app).

```bash
cd landing
npm install
npm run dev        # http://localhost:5175
npm run build      # tsc --noEmit && vite build  → dist/
npm run preview    # serve dist/ on http://localhost:4175
npm run typecheck
```

## The scroll-driven hero

The hero is a live **Three.js** Earth, not a video and not an image. Scrolling
drives a camera along a flight path around and into the globe — the same
technique as Apple's scroll-through product pages, and the mechanic the
`scroll-world` skill is built around. It is implemented directly in WebGL
rather than as a pre-rendered clip chain, so the page needs no render backend,
no API key and no third-party host.

- `src/globe.ts` — the scene: Earth shader (day/night terminator, ocean sun
  glint, atmosphere rim), starfield, the pilot-region marker, and the scroll
  keyframes.
- `src/main.ts` — wiring: scroll → camera, the route rail, reveal animations,
  reduced-motion, and the WebGL fallback.
- `src/styles.css` — layout and theme, using the same tokens as the app.

Camera keys sit on the *middle* of each beat's pinned window, so the camera has
settled by the time the copy holds still. Type is sized in `min(vw, vh)` so the
copy always fits the pinned frame on short windows.

`window.__ICARUS__` is exposed for verification (`progress`, `frames`, `webgl`,
`rendered`, `sections`, `reducedMotion`, `href`).

## Textures

`public/earth/` holds NASA imagery, downscaled — all public domain, all served
locally so the page makes no external request (the same property
`web/e2e/no-third-party.spec.ts` guards for the app):

| File | Source |
|---|---|
| `earth-blue-marble.jpg` | NASA Blue Marble, daytime true colour |
| `earth-night.jpg` | NASA Black Marble, city lights |
| `earth-topology.png` | NASA/GEBCO relief, used as a light bump |
| `earth-water.png` | ocean mask, used for the sun glint |

See `docs/REFERENCES.md` for the dataset bibliography.

## Accessibility

`axe-core` reports 0 violations (31 passes) on the built page. The remaining
"incomplete: color-contrast" item is axe declining to compute a background
behind a fixed full-page canvas, not a failure. The globe is `aria-hidden`;
the marker chip is too, since it is a visual annotation of that globe and the
pilot region is named in the copy.
