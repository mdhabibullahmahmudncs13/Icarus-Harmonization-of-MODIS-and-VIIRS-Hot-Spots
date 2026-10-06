import { createGlobe, PILOT_REGION } from './globe';
import type { Globe } from './globe';

/**
 * Scroll drives the camera (the scroll-world mechanic), the rail reports where
 * you are in the journey, and the pilot-region chip tracks the globe.
 */

const canvas = document.getElementById('world') as HTMLCanvasElement | null;
const progressBar = document.getElementById('progress-bar');
const railList = document.getElementById('rail-list');
const beats = Array.from(document.querySelectorAll<HTMLElement>('.beat'));

const reduceQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
let reducedMotion = reduceQuery.matches;

let progress = 0;
let frames = 0;
let globe: Globe | null = null;
let markerChip: HTMLDivElement | null = null;

function readProgress(): number {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  if (max <= 0) return 0;
  return Math.min(1, Math.max(0, window.scrollY / max));
}

function applyProgress() {
  progress = readProgress();
  globe?.setProgress(progress);
  if (progressBar) progressBar.style.width = `${(progress * 100).toFixed(2)}%`;
  updateActiveBeat();
}

// --- rail ----------------------------------------------------------------
let railButtons: HTMLButtonElement[] = [];

function buildRail() {
  if (!railList) return;
  beats.forEach((beat, index) => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.innerHTML = `<span class="rail__label">${beat.dataset.title ?? `Beat ${index + 1}`}</span>`;
    button.setAttribute('aria-label', `Go to ${beat.dataset.title ?? `section ${index + 1}`}`);
    button.addEventListener('click', () => {
      beat.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' });
    });
    item.appendChild(button);
    railList.appendChild(item);
    railButtons.push(button);
  });
}

function updateActiveBeat() {
  const probe = window.innerHeight * 0.5;
  let active = 0;
  beats.forEach((beat, index) => {
    const rect = beat.getBoundingClientRect();
    if (rect.top <= probe) active = index;
  });
  railButtons.forEach((button, index) => {
    button.parentElement?.classList.toggle('is-active', index === active);
  });
}

// --- reveal --------------------------------------------------------------
function observeReveals() {
  const targets = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'));
  if (reducedMotion) {
    targets.forEach((target) => target.classList.add('is-visible'));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { rootMargin: '-18% 0px -18% 0px' },
  );
  targets.forEach((target) => observer.observe(target));
}

// --- boot ----------------------------------------------------------------
function boot() {
  buildRail();
  observeReveals();

  if (canvas) {
    try {
      const created = createGlobe(canvas);
      globe = created.globe;
      globe.setReducedMotion(reducedMotion);
      created.start();
      created.globe.resize();

      markerChip = document.createElement('div');
      markerChip.className = 'marker-chip';
      // A visual annotation of a decorative globe: keep it out of the a11y tree.
      markerChip.setAttribute('aria-hidden', 'true');
      markerChip.textContent = `${PILOT_REGION.label} · ${PILOT_REGION.lat.toFixed(1)}°N ${PILOT_REGION.lon.toFixed(1)}°E`;
      document.body.appendChild(markerChip);

      const trackMarker = () => {
        frames += 1;
        if (markerChip && globe) {
          const position = globe.markerScreenPosition();
          markerChip.style.transform = `translate(${position.x}px, ${position.y}px) translate(-50%, -140%)`;
          markerChip.classList.toggle('is-visible', position.visible);
        }
        requestAnimationFrame(trackMarker);
      };
      requestAnimationFrame(trackMarker);
    } catch (error) {
      console.warn('WebGL unavailable, falling back to a static hero.', error);
      document.body.classList.add('no-webgl');
    }
  }

  window.addEventListener('scroll', applyProgress, { passive: true });
  window.addEventListener('resize', () => {
    globe?.resize();
    applyProgress();
  });
  reduceQuery.addEventListener('change', (event) => {
    reducedMotion = event.matches;
    globe?.setReducedMotion(reducedMotion);
  });

  applyProgress();

  // Verification hook: proves in a browser that WebGL really rendered.
  Object.defineProperty(window, '__ICARUS__', {
    value: {
      get progress() {
        return progress;
      },
      get frames() {
        return frames;
      },
      get webgl() {
        return globe !== null;
      },
      get rendered() {
        return canvas?.dataset.rendered === 'true';
      },
      get sections() {
        return beats.length;
      },
      get reducedMotion() {
        return reducedMotion;
      },
      get href() {
        const link = document.querySelector<HTMLAnchorElement>('[data-app-link]');
        return link?.href ?? null;
      },
    },
    configurable: true,
  });
}

boot();
