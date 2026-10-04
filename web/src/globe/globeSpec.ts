/**
 * Reconstruction spec for the hero globe.
 *
 * This is the model's parameter sheet, kept separate from the renderer
 * objects so a change here is a change to the object, not to a side effect
 * inside the scene graph. Geometry is authored from code only — a procedural
 * dot-matrix Earth, no downloaded meshes, no image textures.
 *
 * Scale: the unit sphere is 1.0 world unit = 6 371 km (Earth radius).
 */
import type { Mode } from "../state/urlState";

export interface GlobeSpec {
  earth: {
    radius: number;
    /** Sphere body sits just under the dot shell so it occludes the far side. */
    bodyRadius: number;
    bodyColor: number;
    atmosphereRadius: number;
    atmosphereColor: number;
    atmosphereOpacity: number;
  };
  landDots: {
    /** World-space dot size at radius 1; land cells are 1° apart (0.017 45 u). */
    size: number;
    color: number;
    opacity: number;
  };
  hotspots: {
    /** Dots sit on a slightly larger shell so they never z-fight the body. */
    radius: number;
    /**
     * The busiest N cells are the ones the globe draws, ranked by the higher of
     * the two counts so the set does not change when the mode is toggled. At
     * full region density the dots merge into one white patch with no readable
     * structure; the panel and the JSON carry every cell. Disclosed in the hero
     * legend.
     */
    maxDots: number;
    baseSize: number;
    /** Size multiplier for the quietest cell; keeps a 1-detection cell visible. */
    floorScale: number;
    /** Size multiplier for the single busiest cell in the active mode. */
    peakScale: number;
    color: number;
    opacity: number;
  };
  beams: {
    count: number;
    minLength: number;
    maxLength: number;
    baseRadius: number;
    tipRadius: number;
    color: number;
    opacity: number;
  };
  graticule: {
    radius: number;
    color: number;
    opacity: number;
    latStep: number;
    lonStep: number;
  };
  orbit: {
    radius: number;
    tilt: number;
    color: number;
    opacity: number;
  };
  regionOutline: {
    radius: number;
    color: number;
    opacity: number;
  };
  stars: {
    count: number;
    seed: number;
    color: number;
    opacity: number;
    minRadius: number;
    maxRadius: number;
  };
  view: {
    fov: number;
    near: number;
    far: number;
    /** Default camera distance from the globe centre. */
    distance: number;
    minDistance: number;
    maxDistance: number;
    /** Camera distance when the study region is framed. */
    regionDistance: number;
    /** Resting tilt for the wide view (radians, tilts the north pole toward the camera). */
    restPitch: number;
    /** Auto-rotation speed, radians per second. */
    spin: number;
    /** Seconds the globe keeps its heading after a drag or a fly-to. */
    spinResumeDelay: number;
  };
  motion: {
    /** Duration of a fly-to / reset move, seconds. */
    flySeconds: number;
    /** Duration of the raw↔harmonized dot-size morph, seconds (matches the chart). */
    modeSeconds: number;
    /** Breathing period for hotspot dots, seconds. */
    pulseSeconds: number;
  };
}

export const GLOBE_SPEC: GlobeSpec = {
  earth: {
    radius: 1,
    bodyRadius: 0.9975,
    bodyColor: 0x04170f,
    atmosphereRadius: 1.055,
    atmosphereColor: 0x2ef07a,
    atmosphereOpacity: 0.5,
  },
  landDots: {
    size: 0.0072,
    color: 0x2ee87d,
    opacity: 0.85,
  },
  hotspots: {
    radius: 1.004,
    maxDots: 500,
    baseSize: 0.0085,
    floorScale: 0.3,
    peakScale: 2.2,
    color: 0xd6ffe8,
    opacity: 0.9,
  },
  beams: {
    count: 18,
    minLength: 0.2,
    maxLength: 0.66,
    baseRadius: 0.0035,
    tipRadius: 0.011,
    color: 0xd8ffe8,
    opacity: 0.65,
  },
  graticule: {
    radius: 1.0015,
    color: 0x1c8f52,
    opacity: 0.3,
    latStep: 15,
    lonStep: 15,
  },
  orbit: {
    radius: 1.52,
    tilt: 1.22,
    color: 0x2ee87d,
    opacity: 0.22,
  },
  regionOutline: {
    radius: 1.006,
    color: 0x8dffb8,
    opacity: 0.85,
  },
  stars: { count: 420, seed: 2050, color: 0x9fe6bd, opacity: 0.55, minRadius: 3.4, maxRadius: 11 },
  view: {
    fov: 38,
    near: 0.05,
    far: 60,
    distance: 3.5,
    minDistance: 1.35,
    maxDistance: 5,
    regionDistance: 2.4,
    restPitch: 0.34,
    spin: 0.075,
    spinResumeDelay: 3.5,
  },
  motion: {
    flySeconds: 1.05,
    modeSeconds: 0.7,
    pulseSeconds: 3.2,
  },
};

/** A grid cell rendered as one glowing dot, positioned by its own coordinates. */
export interface GlobeSpot {
  id: string;
  lat: number;
  lon: number;
  raw: number;
  harmonized: number;
}

export function spotValue(spot: GlobeSpot, mode: Mode): number {
  return mode === "raw" ? spot.raw : spot.harmonized;
}
