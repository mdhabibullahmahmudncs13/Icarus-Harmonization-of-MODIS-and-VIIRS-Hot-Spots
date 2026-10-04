/**
 * GlobeHero — mounts the procedural Earth and keeps it honest.
 *
 * The canvas is decoration around real payload numbers: every glowing dot is
 * one grid cell from the active data source at its own coordinates, sized by
 * its count in the current Raw | Harmonized mode. The component owns the
 * render loop, the pointer drag, the resize observer and the WebGL lifetime;
 * the scene itself is compiled in `../globe/createEarthGlobe`.
 *
 * The camera state is owned by the caller (`view`) and only ever *applied*
 * to the scene here, so the globe is a mirror of the page, not a second
 * source of truth.
 *
 * If WebGL is unavailable (older browser, blocked context, headless run) the
 * hero degrades to a labelled note rather than an empty box, and the rest of
 * the page — chart, panel, provenance — is unaffected.
 */
import { useCallback, useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { createEarthGlobe, type EarthGlobe } from "../globe/createEarthGlobe";
import { getLandMask } from "../globe/landmask";
import type { GlobeSpot } from "../globe/globeSpec";
import type { Mode } from "../state/urlState";

/** What the camera is looking at. Owned by the page, applied to the scene. */
export type GlobeView =
  { kind: "earth" } | { kind: "region" } | { kind: "cell"; id: string; lat: number; lon: number };

export interface GlobeHeroProps {
  hotspots: GlobeSpot[];
  regionBounds: readonly [number, number, number, number];
  mode: Mode;
  view: GlobeView;
  onViewChange: (view: GlobeView) => void;
  /** Overlay content (headline, lede) drawn above the canvas. */
  children?: ReactNode;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** One-off probe, released immediately, so the fallback needs no state update. */
function supportsWebgl(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const probe = document.createElement("canvas");
    const context = probe.getContext("webgl2") ?? probe.getContext("webgl");
    if (context === null) return false;
    // Browsers cap live WebGL contexts; give this one straight back.
    (context.getExtension("WEBGL_lose_context") as { loseContext(): void } | null)?.loseContext();
    return true;
  } catch {
    return false;
  }
}

function applyView(globe: EarthGlobe, view: GlobeView): void {
  if (view.kind === "earth") globe.resetView();
  else if (view.kind === "region") globe.focusRegion();
  else globe.focusOn(view.lat, view.lon);
}

export function GlobeHero({
  hotspots,
  regionBounds,
  mode,
  view,
  onViewChange,
  children,
}: GlobeHeroProps): ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const globeRef = useRef<EarthGlobe | null>(null);
  const [failed, setFailed] = useState<boolean>(() => !supportsWebgl());

  // The scene effect must not re-run when the toggle or the camera moves, so
  // it reads the newest props from a ref that is synced in its own effect.
  const latest = useRef({ mode, view });
  useEffect(() => {
    latest.current = { mode, view };
  }, [mode, view]);

  useEffect(() => {
    if (failed) return;
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (canvas === null || container === null || hotspots.length === 0) return;

    let globe: EarthGlobe;
    try {
      globe = createEarthGlobe({
        canvas,
        hotspots,
        regionBounds,
        mode: latest.current.mode,
        landMask: getLandMask(),
        reducedMotion: prefersReducedMotion(),
      });
    } catch (error) {
      console.error("Icarus: the globe could not start.", error);
      // Report on the next frame instead of synchronously inside this effect.
      const handle = requestAnimationFrame(() => setFailed(true));
      return () => cancelAnimationFrame(handle);
    }
    globeRef.current = globe;
    applyView(globe, latest.current.view);

    const applySize = (): void => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      globe.setSize(container.clientWidth, container.clientHeight, dpr);
    };
    applySize();

    let raf = 0;
    let last = performance.now();
    let visible = true;
    const start = last;

    const frame = (now: number): void => {
      const delta = (now - last) / 1000;
      last = now;
      globe.render((now - start) / 1000, delta);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    const resizeObserver = new ResizeObserver(applySize);
    resizeObserver.observe(container);

    // Stop drawing while the hero is off-screen; the chart is the thing being
    // read by then, and an invisible WebGL loop is pure battery drain.
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting === visible) continue;
          visible = entry.isIntersecting;
          if (visible) {
            last = performance.now();
            raf = requestAnimationFrame(frame);
          } else {
            cancelAnimationFrame(raf);
          }
        }
      },
      { threshold: 0.01 },
    );
    intersectionObserver.observe(container);

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMotionChange = (event: MediaQueryListEvent): void =>
      globe.setReducedMotion(event.matches);
    motionQuery.addEventListener("change", onMotionChange);

    return () => {
      cancelAnimationFrame(raf);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      motionQuery.removeEventListener("change", onMotionChange);
      globe.dispose();
      globeRef.current = null;
    };
  }, [hotspots, regionBounds, failed]);

  useEffect(() => {
    globeRef.current?.setMode(mode);
  }, [mode]);

  useEffect(() => {
    const globe = globeRef.current;
    if (globe !== null) applyView(globe, view);
  }, [view]);

  // Pointer drag: grab and spin the globe.
  const drag = useRef<{ x: number; y: number } | null>(null);
  const onPointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    drag.current = { x: event.clientX, y: event.clientY };
    event.currentTarget.setPointerCapture(event.pointerId);
  }, []);
  const onPointerMove = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const from = drag.current;
    if (from === null) return;
    globeRef.current?.orbitBy(event.clientX - from.x, event.clientY - from.y);
    drag.current = { x: event.clientX, y: event.clientY };
  }, []);
  const endDrag = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  return (
    <div className="globe" ref={containerRef}>
      <div
        className="globe-stage"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        data-testid="globe-stage"
      >
        <canvas ref={canvasRef} className="globe-canvas" aria-hidden="true" />
        {failed && (
          <div className="globe-fallback" data-testid="globe-fallback">
            <p>
              This browser could not start WebGL, so the globe is not drawn. Everything below is
              unaffected.
            </p>
          </div>
        )}
      </div>

      {children}

      <div className="globe-controls">
        <button
          type="button"
          className="ghost-btn"
          aria-pressed={view.kind === "region"}
          onClick={() => onViewChange({ kind: "region" })}
        >
          Study region
        </button>
        <button
          type="button"
          className="ghost-btn"
          aria-pressed={view.kind === "earth"}
          onClick={() => onViewChange({ kind: "earth" })}
        >
          Whole Earth
        </button>
        <span className="globe-hint">Drag to rotate</span>
      </div>

      <p className="visually-hidden">
        A slowly rotating three-dimensional Earth. Each glowing dot is one 5.5 km grid cell that
        contains detections in the mock dataset, placed at the cell's own coordinates inside the
        outlined study region; the busiest cells also carry a light beam. The equivalent numbers are
        listed in the hottest-cells panel beside the globe.
      </p>
    </div>
  );
}
