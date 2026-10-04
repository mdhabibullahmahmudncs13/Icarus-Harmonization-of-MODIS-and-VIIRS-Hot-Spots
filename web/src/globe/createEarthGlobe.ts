/**
 * createEarthGlobe — the hero globe as a code-built Three.js object.
 *
 * Reconstructed procedurally from the direction reference (a dark,
 * neon-green Earth): a near-black sphere body, a 1° dot-matrix land shell
 * (Natural Earth mask, generated offline by `scripts/gen-landmask.ts`), a
 * faint lat/lon graticule, one tilted orbit ring, and the study-region grid
 * cells as glowing dots with light beams on the busiest ones.
 *
 * Reconstruction data lives in `globeSpec.ts`; this file only turns it into
 * renderer objects. Nothing here reads the network, the DOM (beyond the
 * canvas it is handed) or the clipboard — it is a pure function of its
 * options, so the same options always build the same scene.
 */
import {
  AdditiveBlending,
  BackSide,
  BufferAttribute,
  BufferGeometry,
  Color,
  CylinderGeometry,
  DynamicDrawUsage,
  Float32BufferAttribute,
  Group,
  InstancedBufferAttribute,
  InstancedMesh,
  Line,
  LineBasicMaterial,
  LineLoop,
  LineSegments,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  PerspectiveCamera,
  Points,
  Quaternion,
  Scene,
  ShaderMaterial,
  SphereGeometry,
  Vector3,
  WebGLRenderer,
} from "three";
import type { Mode } from "../state/urlState";
import {
  bboxCentre,
  bboxOutline,
  cellCentre,
  graticuleSegments,
  isLand,
  latLonToVec3,
  lerpAngle,
  rotationToFace,
  seededRandom,
  type LandMask,
} from "./geo";
import { GLOBE_SPEC, spotValue, type GlobeSpot } from "./globeSpec";

export interface EarthGlobeOptions {
  canvas: HTMLCanvasElement;
  /** Study-region cells (mock data), placed at their own coordinates. */
  hotspots: GlobeSpot[];
  /** `[west, south, east, north]` of the study region, drawn as a ring. */
  regionBounds: readonly [number, number, number, number];
  mode: Mode;
  landMask: LandMask;
  /** Honour prefers-reduced-motion: no auto-rotation, instant moves. */
  reducedMotion: boolean;
}

export interface EarthGlobe {
  setMode(mode: Mode): void;
  /** React to a change of the prefers-reduced-motion setting at runtime. */
  setReducedMotion(value: boolean): void;
  /** Frame one coordinate and hold the heading. */
  focusOn(lat: number, lon: number, distance?: number): void;
  /** Frame the study region and hold the heading. */
  focusRegion(): void;
  /** Return to the wide, slowly rotating view. */
  resetView(): void;
  /** Drag input, in CSS pixels. */
  orbitBy(dx: number, dy: number): void;
  setSize(cssWidth: number, cssHeight: number, pixelRatio: number): void;
  render(elapsed: number, delta: number): void;
  dispose(): void;
}

const UP = new Vector3(0, 1, 0);

/** Round `desired` to the equivalent angle nearest `current`, so moves take the short way. */
function nearestAngle(current: number, desired: number): number {
  return desired + Math.round((current - desired) / (Math.PI * 2)) * Math.PI * 2;
}

/** Exponentially smoothed step, framerate-independent. */
function approach(current: number, target: number, seconds: number, tau: number): number {
  if (tau <= 0) return target;
  return current + (target - current) * (1 - Math.exp(-seconds / tau));
}

/** Round, soft-edged dot sprite computed in the fragment shader (no texture). */
const DOT_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - vec2(0.5));
    float a = smoothstep(0.5, 0.16, d);
    if (a <= 0.002) discard;
    gl_FragColor = vec4(uColor, a * uOpacity * vAlpha);
  }
`;

const DOT_VERTEX = /* glsl */ `
  attribute float aSize;
  attribute float aAlpha;
  varying float vAlpha;
  uniform float uPointScale;
  void main() {
    vAlpha = aAlpha;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = clamp(aSize * uPointScale / -mv.z, 1.0, 40.0);
  }
`;

const SPOT_VERTEX = /* glsl */ `
  attribute float aRaw;
  attribute float aHarm;
  varying float vAlpha;
  uniform float uPointScale;
  uniform float uBaseSize;
  uniform float uFloorScale;
  uniform float uPeakScale;
  uniform float uMix;
  void main() {
    // sqrt leaves room for the long tail: the median cell holds a fraction of
    // the busiest cell, and a linear ramp would flatten every quiet cell to zero.
    float s = sqrt(mix(aRaw, aHarm, uMix));
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = clamp(uBaseSize * mix(uFloorScale, uPeakScale, s) * uPointScale / -mv.z, 1.0, 34.0);
    vAlpha = mix(0.08, 1.0, s);
  }
`;

function createDotMaterial(color: number, opacity: number): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: {
      uColor: { value: new Color(color) },
      uOpacity: { value: opacity },
      uPointScale: { value: 800 },
    },
    vertexShader: DOT_VERTEX,
    fragmentShader: DOT_FRAGMENT,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: AdditiveBlending,
  });
}

export function createEarthGlobe(options: EarthGlobeOptions): EarthGlobe {
  const spec = GLOBE_SPEC;
  const { canvas, hotspots, regionBounds, landMask } = options;
  let reducedMotion = options.reducedMotion;

  const renderer = new WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: "low-power",
  });
  renderer.setClearAlpha(0);

  const scene = new Scene();
  const camera = new PerspectiveCamera(spec.view.fov, 1, spec.view.near, spec.view.far);
  camera.position.set(0, 0, spec.view.distance);

  /** Everything that turns with the globe (body, dots, graticule, region ring). */
  const globe = new Group();
  globe.rotation.set(spec.view.restPitch, 0, 0);
  scene.add(globe);

  const disposables: { dispose(): void }[] = [];
  const track = <T extends { dispose(): void }>(item: T): T => {
    disposables.push(item);
    return item;
  };

  // --- Body: a near-black sphere that occludes the far hemisphere --------
  const bodyGeometry = track(new SphereGeometry(spec.earth.bodyRadius, 64, 48));
  const bodyMaterial = track(new MeshBasicMaterial({ color: spec.earth.bodyColor }));
  globe.add(new Mesh(bodyGeometry, bodyMaterial));

  // --- Atmosphere: additive rim glow around the silhouette ---------------
  const atmosphereGeometry = track(new SphereGeometry(spec.earth.atmosphereRadius, 48, 32));
  const atmosphereMaterial = track(
    new ShaderMaterial({
      uniforms: {
        uColor: { value: new Color(spec.earth.atmosphereColor) },
        uOpacity: { value: spec.earth.atmosphereOpacity },
      },
      vertexShader: /* glsl */ `
        varying vec3 vNormal;
        varying vec3 vView;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vView = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor;
        uniform float uOpacity;
        varying vec3 vNormal;
        varying vec3 vView;
        void main() {
          float rim = pow(1.0 - abs(dot(normalize(vNormal), normalize(vView))), 3.0);
          gl_FragColor = vec4(uColor, rim * uOpacity);
        }
      `,
      transparent: true,
      side: BackSide,
      depthWrite: false,
      blending: AdditiveBlending,
    }),
  );
  scene.add(new Mesh(atmosphereGeometry, atmosphereMaterial));

  // --- Land shell: one dot per 1° land cell -----------------------------
  const landPositions: number[] = [];
  const landSizes: number[] = [];
  const landAlphas: number[] = [];
  const jitter = seededRandom(2050);
  let landDotCount = 0;
  for (let row = 0; row < landMask.height; row++) {
    for (let col = 0; col < landMask.width; col++) {
      if (!isLand(landMask, row, col)) continue;
      const { lat, lon } = cellCentre(landMask, row, col);
      const [x, y, z] = latLonToVec3(lat, lon, spec.earth.radius);
      landPositions.push(x, y, z);
      landSizes.push(spec.landDots.size * (0.72 + jitter() * 0.7));
      // Slightly dimmer near the poles so the dot field does not pool there.
      landAlphas.push(0.55 + 0.45 * Math.cos((lat * Math.PI) / 180));
      landDotCount++;
    }
  }
  if (landDotCount < landMask.width * landMask.height * 0.05) {
    // A mask that decodes to almost nothing means the generated file is
    // wrong; fail loudly rather than render an empty black ball.
    throw new Error(`Land mask decoded to only ${landDotCount} land cells`);
  }
  const landGeometry = track(new BufferGeometry());
  landGeometry.setAttribute("position", new Float32BufferAttribute(landPositions, 3));
  landGeometry.setAttribute("aSize", new Float32BufferAttribute(landSizes, 1));
  landGeometry.setAttribute("aAlpha", new Float32BufferAttribute(landAlphas, 1));
  const landMaterial = track(createDotMaterial(spec.landDots.color, spec.landDots.opacity));
  globe.add(new Points(landGeometry, landMaterial));

  // --- Hotspot dots: the busiest cells, one dot each, sized by its count --
  // Ranked once by the higher of the two counts, so toggling the mode resizes
  // the dots without adding or removing any of them.
  const ranked = [...hotspots].sort(
    (a, b) => Math.max(b.raw, b.harmonized) - Math.max(a.raw, a.harmonized),
  );
  const spotSet = ranked.slice(0, spec.hotspots.maxDots);
  const peakCount = Math.max(1, ...spotSet.map((s) => Math.max(s.raw, s.harmonized)));
  const spotPositions: number[] = [];
  const spotRaw: number[] = [];
  const spotHarm: number[] = [];
  for (const spot of spotSet) {
    const [x, y, z] = latLonToVec3(spot.lat, spot.lon, spec.hotspots.radius);
    spotPositions.push(x, y, z);
    spotRaw.push(spot.raw / peakCount);
    spotHarm.push(spot.harmonized / peakCount);
  }
  const spotGeometry = track(new BufferGeometry());
  spotGeometry.setAttribute("position", new Float32BufferAttribute(spotPositions, 3));
  spotGeometry.setAttribute("aRaw", new Float32BufferAttribute(spotRaw, 1));
  spotGeometry.setAttribute("aHarm", new Float32BufferAttribute(spotHarm, 1));
  const spotMaterial = track(
    new ShaderMaterial({
      uniforms: {
        uColor: { value: new Color(spec.hotspots.color) },
        uOpacity: { value: spec.hotspots.opacity },
        uPointScale: { value: 800 },
        uBaseSize: { value: spec.hotspots.baseSize },
        uFloorScale: { value: spec.hotspots.floorScale },
        uPeakScale: { value: spec.hotspots.peakScale },
        uMix: { value: options.mode === "harmonized" ? 1 : 0 },
      },
      vertexShader: SPOT_VERTEX,
      fragmentShader: DOT_FRAGMENT,
      transparent: true,
      depthTest: true,
      depthWrite: false,
      blending: AdditiveBlending,
    }),
  );
  globe.add(new Points(spotGeometry, spotMaterial));

  // --- Beams: light streaks on the busiest cells of the active mode ------
  const beamCount = Math.max(1, spec.beams.count);
  const beamGeometry = track(
    new CylinderGeometry(spec.beams.tipRadius, spec.beams.baseRadius, 1, 8, 1, true),
  );
  beamGeometry.translate(0, 0.5, 0);
  // Per-beam tint, as an explicit instanced attribute: naming it `instanceColor`
  // would collide with the declaration three.js already injects for InstancedMesh.
  const beamTint = new InstancedBufferAttribute(new Float32Array(beamCount * 3), 3);
  beamGeometry.setAttribute("beamTint", beamTint);
  const beamMaterial = track(
    new ShaderMaterial({
      uniforms: {
        uColor: { value: new Color(spec.beams.color) },
        uOpacity: { value: spec.beams.opacity },
      },
      vertexShader: /* glsl */ `
        attribute vec3 beamTint;
        varying float vT;
        varying vec3 vTint;
        void main() {
          vT = clamp(position.y, 0.0, 1.0);
          vTint = beamTint;
          gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor;
        uniform float uOpacity;
        varying float vT;
        varying vec3 vTint;
        void main() {
          float fade = pow(1.0 - vT, 1.7);
          gl_FragColor = vec4(uColor * vTint, fade * uOpacity);
        }
      `,
      transparent: true,
      depthTest: true,
      depthWrite: false,
      side: BackSide,
      blending: AdditiveBlending,
    }),
  );
  const beamMesh = new InstancedMesh(beamGeometry, beamMaterial, beamCount);
  beamMesh.frustumCulled = false;
  beamMesh.instanceMatrix.setUsage(DynamicDrawUsage);
  globe.add(beamMesh);

  const beamSpots = ranked.slice(0, spec.beams.count);
  const beamPeak = Math.max(1, ...beamSpots.map((s) => Math.max(s.raw, s.harmonized)));

  const _matrix = new Matrix4();
  const _quat = new Quaternion();
  const _pos = new Vector3();
  const _scale = new Vector3();
  const _zeroScale = new Vector3(0, 0, 0);
  const _normal = new Vector3();

  function updateBeams(mode: Mode): void {
    for (let i = 0; i < beamCount; i++) {
      const spot = beamSpots[i];
      if (spot === undefined) {
        _matrix.compose(_pos.set(0, 0, 0), _quat.identity(), _zeroScale);
        beamMesh.setMatrixAt(i, _matrix);
        beamTint.setXYZ(i, 0, 0, 0);
        continue;
      }
      const v = Math.sqrt(spotValue(spot, mode) / beamPeak);
      const length = spec.beams.minLength + (spec.beams.maxLength - spec.beams.minLength) * v;
      _normal.set(...latLonToVec3(spot.lat, spot.lon, 1)).normalize();
      _quat.setFromUnitVectors(UP, _normal);
      _pos.copy(_normal).multiplyScalar(spec.earth.radius * 0.999);
      _matrix.compose(_pos, _quat, _scale.set(1, length, 1));
      beamMesh.setMatrixAt(i, _matrix);
      beamTint.setXYZ(i, 0.45 + 0.55 * v, 0.7 + 0.3 * v, 0.55 + 0.45 * v);
    }
    beamTint.needsUpdate = true;
    beamMesh.instanceMatrix.needsUpdate = true;
  }
  updateBeams(options.mode);

  // --- Graticule + study-region ring ------------------------------------
  const graticuleGeometry = track(new BufferGeometry());
  graticuleGeometry.setAttribute(
    "position",
    new BufferAttribute(
      graticuleSegments(spec.graticule.radius, spec.graticule.latStep, spec.graticule.lonStep),
      3,
    ),
  );
  const graticuleMaterial = track(
    new LineBasicMaterial({
      color: spec.graticule.color,
      transparent: true,
      opacity: spec.graticule.opacity,
    }),
  );
  globe.add(new LineSegments(graticuleGeometry, graticuleMaterial));

  const outlineGeometry = track(new BufferGeometry());
  outlineGeometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      bboxOutline(regionBounds, spec.regionOutline.radius).flatMap(([x, y, z]) => [x, y, z]),
      3,
    ),
  );
  const outlineMaterial = track(
    new LineBasicMaterial({
      color: spec.regionOutline.color,
      transparent: true,
      opacity: spec.regionOutline.opacity,
    }),
  );
  globe.add(new LineLoop(outlineGeometry, outlineMaterial));

  // --- Orbit ring (world-fixed, so the globe turns inside it) -----------
  const orbitRadius = spec.orbit.radius;
  const orbitGeometry = track(new BufferGeometry());
  orbitGeometry.setAttribute(
    "position",
    new Float32BufferAttribute(
      Array.from({ length: 181 }, (_, i) => {
        const t = (i / 180) * Math.PI * 2;
        return [Math.cos(t) * orbitRadius, 0, Math.sin(t) * orbitRadius];
      }).flat(),
      3,
    ),
  );
  const orbitMaterial = track(
    new LineBasicMaterial({
      color: spec.orbit.color,
      transparent: true,
      opacity: spec.orbit.opacity,
    }),
  );
  const orbit = new Line(orbitGeometry, orbitMaterial);
  orbit.rotation.set(0, -0.4, spec.orbit.tilt);
  scene.add(orbit);

  // --- Starfield --------------------------------------------------------
  const starRandom = seededRandom(spec.stars.seed);
  const starPositions: number[] = [];
  const starSizes: number[] = [];
  const starAlphas: number[] = [];
  for (let i = 0; i < spec.stars.count; i++) {
    const theta = starRandom() * Math.PI * 2;
    const phi = Math.acos(2 * starRandom() - 1);
    const r = spec.stars.minRadius + starRandom() * (spec.stars.maxRadius - spec.stars.minRadius);
    starPositions.push(
      r * Math.sin(phi) * Math.cos(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.sin(theta),
    );
    starSizes.push(0.01 + starRandom() * 0.03);
    starAlphas.push(0.25 + starRandom() * 0.75);
  }
  const starGeometry = track(new BufferGeometry());
  starGeometry.setAttribute("position", new Float32BufferAttribute(starPositions, 3));
  starGeometry.setAttribute("aSize", new Float32BufferAttribute(starSizes, 1));
  starGeometry.setAttribute("aAlpha", new Float32BufferAttribute(starAlphas, 1));
  const starMaterial = track(createDotMaterial(spec.stars.color, spec.stars.opacity));
  scene.add(new Points(starGeometry, starMaterial));

  // --- View state -------------------------------------------------------
  const region = bboxCentre(regionBounds);
  const regionRotation = rotationToFace(region.lat, region.lon);

  let yaw = reducedMotion ? regionRotation.y : 0;
  let pitch = reducedMotion ? regionRotation.x : spec.view.restPitch;
  let targetYaw = yaw;
  let targetPitch = pitch;
  let distance = spec.view.distance;
  let targetDistance = spec.view.distance;
  let focused = false;
  let pausedUntil = 0;
  let elapsed = 0;
  let modeMix = options.mode === "harmonized" ? 1 : 0;
  let targetMix = modeMix;
  let mode: Mode = options.mode;

  function setReducedMotion(value: boolean): void {
    reducedMotion = value;
  }

  function setMode(next: Mode): void {
    if (next === mode) return;
    mode = next;
    targetMix = next === "harmonized" ? 1 : 0;
    updateBeams(next);
  }

  function focusOn(lat: number, lon: number, distance = spec.view.regionDistance): void {
    const rotation = rotationToFace(lat, lon);
    focused = true;
    pausedUntil = Number.POSITIVE_INFINITY;
    targetYaw = nearestAngle(yaw, rotation.y);
    targetPitch = rotation.x;
    targetDistance = distance;
  }

  function focusRegion(): void {
    // Centred but at the wide distance: the whole Earth stays readable, and the
    // region is framed by its own outline instead of filling the frame.
    focusOn(region.lat, region.lon, spec.view.distance);
  }

  function resetView(): void {
    focused = false;
    pausedUntil = elapsed + spec.view.spinResumeDelay;
    targetYaw = yaw;
    targetPitch = spec.view.restPitch;
    targetDistance = spec.view.distance;
  }

  function orbitBy(dx: number, dy: number): void {
    focused = false;
    yaw += dx * 0.005;
    pitch = Math.max(-1.2, Math.min(1.2, pitch + dy * 0.004));
    targetYaw = yaw;
    targetPitch = pitch;
    pausedUntil = elapsed + spec.view.spinResumeDelay;
  }

  function setSize(cssWidth: number, cssHeight: number, pixelRatio: number): void {
    const width = Math.max(1, Math.round(cssWidth));
    const height = Math.max(1, Math.round(cssHeight));
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    // gl_PointSize is in device pixels, so the scale uses the draw-buffer height.
    const pointScale =
      renderer.getContext().drawingBufferHeight / (2 * Math.tan((spec.view.fov * Math.PI) / 360));
    landMaterial.uniforms.uPointScale.value = pointScale;
    spotMaterial.uniforms.uPointScale.value = pointScale;
    starMaterial.uniforms.uPointScale.value = pointScale;
  }

  function render(nextElapsed: number, delta: number): void {
    elapsed = nextElapsed;
    const step = Math.min(0.1, Math.max(0, delta));
    const tau = reducedMotion ? 0 : spec.motion.flySeconds / 4;

    modeMix = approach(modeMix, targetMix, step, tau > 0 ? tau : 1e-6);
    spotMaterial.uniforms.uMix.value = modeMix;

    if (!focused && elapsed > pausedUntil) {
      yaw += spec.view.spin * step;
      targetYaw = yaw;
    }
    yaw = lerpAngle(yaw, targetYaw, tau > 0 ? 1 - Math.exp(-step / tau) : 1);
    pitch = approach(pitch, targetPitch, step, tau);
    distance = approach(distance, targetDistance, step, tau);

    globe.rotation.y = yaw;
    globe.rotation.x = pitch;
    camera.position.set(0, 0, distance);
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
  }

  function dispose(): void {
    for (const item of disposables) item.dispose();
    beamMesh.dispose();
    renderer.dispose();
  }

  return {
    setMode,
    setReducedMotion,
    focusOn,
    focusRegion,
    resetView,
    orbitBy,
    setSize,
    render,
    dispose,
  };
}
