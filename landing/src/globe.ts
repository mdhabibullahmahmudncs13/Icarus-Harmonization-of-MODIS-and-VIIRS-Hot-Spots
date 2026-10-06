import * as THREE from 'three';

/**
 * The hero visual: a real-time 3D Earth.
 *
 * This is the scroll-world technique — scroll drives a camera along a flight
 * path — implemented with a live Three.js globe rather than a pre-rendered
 * video chain, so the page needs no render backend and no third-party host.
 *
 * The textures are NASA imagery (Blue Marble day, Black Marble night, GEBCO
 * relief, ocean mask), downscaled and served from `public/earth/`.
 */

const EARTH_TEXTURES = {
  day: '/earth/earth-blue-marble.jpg',
  night: '/earth/earth-night.jpg',
  relief: '/earth/earth-topology.png',
  water: '/earth/earth-water.png',
};

/** Centre of the pilot region (the API's default bbox: 20–27°N, 88–93°E). */
export const PILOT_REGION = { lat: 23.5, lon: 90.5, label: 'Pilot region' };

/** Direction *toward* the sun, in world space. Fixed so the terminator is stable. */
const SUN_DIRECTION = new THREE.Vector3(-0.55, 0.38, 0.84).normalize();

/** Let the sun sit a touch off the camera axis so the globe reads as lit, not flat. */
const sunLightDir = SUN_DIRECTION.clone();

/**
 * Camera flight path, keyed on page scroll progress (0 → 1). Piecewise-linear
 * between keys, then damped per frame, so the camera glides rather than snaps.
 */
const FLIGHT: { p: number; pos: [number, number, number]; look: [number, number, number] }[] = [
  // The keys sit on the *middle* of each beat's pinned window, so the camera
  // has settled by the time the copy is holding still.
  // Odd beats put the copy left, so the globe is aimed right of centre (a
  // negative look-x), and vice versa.
  { p: 0.0, pos: [-0.5, 0.42, 4.6], look: [-0.85, 0.02, 0] },
  { p: 0.16, pos: [0.9, 0.85, 5.0], look: [0.9, 0.02, 0] },
  { p: 0.33, pos: [-2.6, 0.7, 3.4], look: [-0.5, 0.02, 0] },
  { p: 0.5, pos: [2.5, 0.4, 3.4], look: [0.5, 0.02, 0] },
  { p: 0.66, pos: [-0.9, 0.3, 2.7], look: [-0.55, 0.12, 0] },
  { p: 0.83, pos: [1.7, 1.7, 3.2], look: [0.5, 0.05, 0] },
  { p: 1.0, pos: [0.0, 0.55, 4.7], look: [0.0, 0.0, 0] },
];

/** Spin the globe a little as the page advances, so later beats show new ground. */
const SCROLL_SPIN = 1.5;

const DEG = Math.PI / 180;

function latLonToVector3(lat: number, lon: number, radius = 1): THREE.Vector3 {
  const phi = (90 - lat) * DEG;
  const theta = (lon + 180) * DEG;
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

const EARTH_VERTEX = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    vUv = uv;
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vec4 worldPosition = modelMatrix * vec4(position, 1.0);
    vPosW = worldPosition.xyz;
    gl_Position = projectionMatrix * viewMatrix * worldPosition;
  }
`;

const EARTH_FRAGMENT = /* glsl */ `
  uniform sampler2D uDay;
  uniform sampler2D uNight;
  uniform sampler2D uRelief;
  uniform sampler2D uWater;
  uniform vec3 uSunDir;
  uniform float uNightGain;

  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;

  void main() {
    vec3 n = normalize(vNormalW);
    vec3 viewDir = normalize(cameraPosition - vPosW);

    // Day/night terminator: a soft band rather than a hard line.
    float sun = dot(n, uSunDir);
    float dayMix = smoothstep(-0.14, 0.30, sun);
    float diffuse = clamp(sun, 0.0, 1.0);

    vec3 day = texture2D(uDay, vUv).rgb;
    vec3 night = texture2D(uNight, vUv).rgb;
    float relief = texture2D(uRelief, vUv).r;
    float water = texture2D(uWater, vUv).r;

    // Cheap relief: the day map already carries shading; nudge it for texture.
    day *= mix(0.93, 1.07, relief);

    vec3 lit = day * (0.10 + 1.0 * diffuse);

    // Sun glint, oceans only.
    vec3 halfVec = normalize(viewDir + uSunDir);
    float spec = pow(max(dot(n, halfVec), 0.0), 62.0) * water * diffuse;
    lit += vec3(1.0, 0.97, 0.9) * spec * 0.85;

    // Atmosphere rim on the lit limb.
    float rim = pow(clamp(1.0 - max(dot(n, viewDir), 0.0), 0.0, 1.0), 3.0);
    vec3 atmosphere = vec3(0.34, 0.58, 1.0) * rim * (0.28 + 0.72 * dayMix);

    vec3 colour = mix(night * uNightGain, lit, dayMix) + atmosphere;
    gl_FragColor = vec4(colour, 1.0);

    #include <colorspace_fragment>
  }
`;

const ATMOSPHERE_VERTEX = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vec4 worldPosition = modelMatrix * vec4(position, 1.0);
    vPosW = worldPosition.xyz;
    gl_Position = projectionMatrix * viewMatrix * worldPosition;
  }
`;

const ATMOSPHERE_FRAGMENT = /* glsl */ `
  uniform vec3 uSunDir;
  uniform vec3 uColor;
  uniform float uIntensity;

  varying vec3 vNormalW;
  varying vec3 vPosW;

  void main() {
    vec3 n = normalize(vNormalW);
    vec3 viewDir = normalize(cameraPosition - vPosW);
    float rim = pow(clamp(1.0 - abs(dot(n, viewDir)), 0.0, 1.0), 2.4);
    float sun = clamp(dot(n, uSunDir), 0.0, 1.0);
    float alpha = rim * (0.18 + 1.0 * sun) * uIntensity;
    gl_FragColor = vec4(uColor, alpha);

    #include <colorspace_fragment>
  }
`;

const STAR_VERTEX = /* glsl */ `
  attribute float aSize;
  attribute float aPhase;
  attribute vec3 aColor;
  uniform float uTime;
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    vColor = aColor;
    vAlpha = 0.45 + 0.55 * (0.5 + 0.5 * sin(uTime * 0.6 + aPhase * 6.283));
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize;
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const STAR_FRAGMENT = /* glsl */ `
  varying vec3 vColor;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    float a = smoothstep(0.5, 0.02, d) * vAlpha;
    if (a < 0.01) discard;
    gl_FragColor = vec4(vColor, a);
    #include <colorspace_fragment>
  }
`;

export interface MarkerScreenPosition {
  x: number;
  y: number;
  visible: boolean;
}

export interface Globe {
  /** Apply the page's scroll progress (0 → 1) as the camera's flight position. */
  setProgress(progress: number): void;
  /** Where the pilot-region marker is on screen, for the HTML chip. */
  markerScreenPosition(): MarkerScreenPosition;
  setReducedMotion(reduced: boolean): void;
  resize(): void;
  dispose(): void;
}

interface GlobeInternals {
  globe: Globe;
  start(): void;
  setVisible(visible: boolean): void;
}

/** Creates the scene, appends it to `canvas`, and starts the render loop. */
export function createGlobe(canvas: HTMLCanvasElement): GlobeInternals {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance',
  });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 400);
  camera.position.set(0, 0.55, 3.05);

  const loader = new THREE.TextureLoader();
  const load = (url: string, srgb: boolean) => {
    const texture = loader.load(url);
    texture.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    return texture;
  };

  const dayMap = load(EARTH_TEXTURES.day, true);
  const nightMap = load(EARTH_TEXTURES.night, true);
  const reliefMap = load(EARTH_TEXTURES.relief, false);
  const waterMap = load(EARTH_TEXTURES.water, false);
  dayMap.anisotropy = renderer.capabilities.getMaxAnisotropy();

  const earthGroup = new THREE.Group();
  scene.add(earthGroup);

  const earthUniforms: Record<string, THREE.IUniform> = {
    uDay: { value: dayMap },
    uNight: { value: nightMap },
    uRelief: { value: reliefMap },
    uWater: { value: waterMap },
    uSunDir: { value: sunLightDir.clone() },
    uNightGain: { value: 1.35 },
  };

  const earth = new THREE.Mesh(
    new THREE.SphereGeometry(1, 96, 64),
    new THREE.ShaderMaterial({
      uniforms: earthUniforms,
      vertexShader: EARTH_VERTEX,
      fragmentShader: EARTH_FRAGMENT,
    }),
  );
  earthGroup.add(earth);

  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(1.035, 96, 64),
    new THREE.ShaderMaterial({
      uniforms: {
        uSunDir: { value: sunLightDir.clone() },
        uColor: { value: new THREE.Color(0x7fb2ff) },
        uIntensity: { value: 1.15 },
      },
      vertexShader: ATMOSPHERE_VERTEX,
      fragmentShader: ATMOSPHERE_FRAGMENT,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      transparent: true,
      depthWrite: false,
    }),
  );
  earthGroup.add(atmosphere);

  // --- pilot-region marker (a child, so it rotates with the globe) ---------
  const markerLocal = latLonToVector3(PILOT_REGION.lat, PILOT_REGION.lon, 1.004);
  const markerNormal = markerLocal.clone().normalize();

  const marker = new THREE.Group();
  marker.position.copy(markerLocal);
  marker.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), markerNormal);
  earthGroup.add(marker);

  const ringMaterial = new THREE.MeshBasicMaterial({
    color: 0xc4f43a,
    transparent: true,
    opacity: 0.85,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.055, 0.075, 48), ringMaterial);
  marker.add(ring);

  const pulseMaterial = new THREE.MeshBasicMaterial({
    color: 0xc4f43a,
    transparent: true,
    opacity: 0.5,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const pulse = new THREE.Mesh(new THREE.RingGeometry(0.06, 0.072, 48), pulseMaterial);
  marker.add(pulse);

  const dotMaterial = new THREE.MeshBasicMaterial({
    color: 0xeaffb0,
    transparent: true,
  });
  const dot = new THREE.Mesh(new THREE.SphereGeometry(0.012, 16, 12), dotMaterial);
  marker.add(dot);

  // Aim the pilot region at the hero camera, then spin with scroll.
  const baseYaw = Math.atan2(-markerLocal.x, markerLocal.z);
  earthGroup.rotation.y = baseYaw;

  // --- starfield ----------------------------------------------------------
  const STAR_COUNT = 2200;
  const starGeometry = new THREE.BufferGeometry();
  const positions = new Float32Array(STAR_COUNT * 3);
  const sizes = new Float32Array(STAR_COUNT);
  const phases = new Float32Array(STAR_COUNT);
  const colours = new Float32Array(STAR_COUNT * 3);
  const tint = new THREE.Color();
  for (let i = 0; i < STAR_COUNT; i += 1) {
    const r = 34 + Math.random() * 70;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.cos(phi);
    positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
    sizes[i] = 0.8 + Math.random() * 2.0;
    phases[i] = Math.random();
    tint.setHSL(0.55 + Math.random() * 0.08, 0.35, 0.72 + Math.random() * 0.25);
    colours[i * 3] = tint.r;
    colours[i * 3 + 1] = tint.g;
    colours[i * 3 + 2] = tint.b;
  }
  starGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  starGeometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  starGeometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  starGeometry.setAttribute('aColor', new THREE.BufferAttribute(colours, 3));

  const starUniforms: Record<string, THREE.IUniform> = { uTime: { value: 0 } };
  const stars = new THREE.Points(
    starGeometry,
    new THREE.ShaderMaterial({
      uniforms: starUniforms,
      vertexShader: STAR_VERTEX,
      fragmentShader: STAR_FRAGMENT,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  );
  scene.add(stars);

  // --- scroll-driven camera ----------------------------------------------
  let targetProgress = 0;
  let smoothProgress = 0;
  let reducedMotion = false;
  let running = true;
  let lastTime = performance.now();
  let elapsed = 0;
  let frames = 0;

  const camPos = new THREE.Vector3();
  const camLook = new THREE.Vector3();
  const lookTarget = new THREE.Vector3();

  function sampleFlight(p: number) {
    const clamped = Math.min(1, Math.max(0, p));
    let a = FLIGHT[0];
    let b = FLIGHT[FLIGHT.length - 1];
    for (let i = 0; i < FLIGHT.length - 1; i += 1) {
      if (clamped >= FLIGHT[i].p && clamped <= FLIGHT[i + 1].p) {
        a = FLIGHT[i];
        b = FLIGHT[i + 1];
        break;
      }
    }
    const span = b.p - a.p || 1;
    const t = (clamped - a.p) / span;
    const ease = t * t * (3 - 2 * t);
    camPos.set(
      a.pos[0] + (b.pos[0] - a.pos[0]) * ease,
      a.pos[1] + (b.pos[1] - a.pos[1]) * ease,
      a.pos[2] + (b.pos[2] - a.pos[2]) * ease,
    );
    const al = a.look;
    const bl = b.look;
    camLook.set(
      al[0] + (bl[0] - al[0]) * ease,
      al[1] + (bl[1] - al[1]) * ease,
      al[2] + (bl[2] - al[2]) * ease,
    );
  }

  function resize() {
    const width = canvas.clientWidth || window.innerWidth;
    const height = canvas.clientHeight || window.innerHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    // Pull back on narrow screens so the globe keeps its margins.
    const fit = Math.min(1, Math.max(0.62, width / 1180));
    camera.fov = 38 / fit;
    camera.updateProjectionMatrix();
  }

  function frame(now: number) {
    if (!running) return;
    const dt = Math.min(0.05, (now - lastTime) / 1000);
    lastTime = now;
    elapsed += dt;
    frames += 1;

    smoothProgress += (targetProgress - smoothProgress) * (reducedMotion ? 1 : 0.075);
    sampleFlight(smoothProgress);

    camera.position.lerp(camPos, reducedMotion ? 1 : 0.16);
    lookTarget.copy(camLook);
    camera.lookAt(lookTarget);

    const spin = smoothProgress * SCROLL_SPIN + (reducedMotion ? 0 : elapsed * 0.012);
    earthGroup.rotation.y += (baseYaw + spin - earthGroup.rotation.y) * (reducedMotion ? 1 : 0.1);

    if (!reducedMotion) {
      const pulseT = (elapsed % 2.2) / 2.2;
      const scale = 1 + pulseT * 1.5;
      pulse.scale.setScalar(scale);
      pulseMaterial.opacity = 0.5 * (1 - pulseT);
      starUniforms['uTime'].value = elapsed;
      stars.rotation.y = elapsed * 0.008 + smoothProgress * 0.25;
      atmosphere.scale.setScalar(1 + Math.sin(elapsed * 0.5) * 0.004);
    } else {
      pulseMaterial.opacity = 0.4;
      pulse.scale.setScalar(1.2);
    }

    // Keep the marker readable: fade the pulsing ring as it turns away.
    marker.getWorldPosition(markerScreenPos);
    const facing = markerNormal
      .clone()
      .applyQuaternion(earthGroup.quaternion)
      .dot(camera.position.clone().normalize());
    const alpha = THREE.MathUtils.clamp((facing - 0.05) / 0.35, 0, 1);
    ringMaterial.opacity = 0.85 * alpha;
    dotMaterial.opacity = alpha;
    markerFacing = alpha > 0.05;

    renderer.render(scene, camera);
    if (frames === 1) canvas.dataset.rendered = 'true';
    requestAnimationFrame(frame);
  }

  const markerScreenPos = new THREE.Vector3();
  let markerFacing = true;

  const globe: Globe = {
    setProgress(progress: number) {
      targetProgress = progress;
    },
    markerScreenPosition() {
      if (!markerFacing) return { x: 0, y: 0, visible: false };
      const projected = markerScreenPos.clone().project(camera);
      const width = canvas.clientWidth || window.innerWidth;
      const height = canvas.clientHeight || window.innerHeight;
      return {
        x: (projected.x * 0.5 + 0.5) * width,
        y: (-projected.y * 0.5 + 0.5) * height,
        visible: projected.z < 1,
      };
    },
    setReducedMotion(reduced: boolean) {
      reducedMotion = reduced;
    },
    resize,
    dispose() {
      running = false;
      renderer.dispose();
      earth.geometry.dispose();
      atmosphere.geometry.dispose();
      starGeometry.dispose();
      dayMap.dispose();
      nightMap.dispose();
      reliefMap.dispose();
      waterMap.dispose();
    },
  };

  resize();

  return {
    globe,
    start() {
      running = true;
      lastTime = performance.now();
      requestAnimationFrame(frame);
    },
    setVisible(visible: boolean) {
      running = visible;
      if (visible) {
        lastTime = performance.now();
        requestAnimationFrame(frame);
      }
    },
  };
}
