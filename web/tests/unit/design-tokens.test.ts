/**
 * Contrast tests driven by the real tokens in src/styles/tokens.css.
 *
 * Reading the values from the stylesheet means the test cannot drift from
 * the design system: change a colour and the ratios are recomputed. The
 * thresholds are WCAG 2.2 ratios, not values tuned to pass.
 *
 * The glass tiles are semi-transparent, so their effective background is
 * computed by blending the fill over the canvas rather than measured from a
 * screenshot (which is a fragile proxy).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "src/styles/tokens.css"), "utf8");

function token(name: string): string {
  const match = css.match(new RegExp(`${name}:\\s*([^;]+);`));
  if (!match || match[1] === undefined) throw new Error(`token ${name} not found`);
  return match[1].trim();
}

function parseColour(value: string): [number, number, number, number] {
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (hex?.[1] !== undefined) {
    const n = parseInt(hex[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const rgba = value.match(/rgba?\(([^)]+)\)/);
  if (rgba?.[1] !== undefined) {
    const [r, g, b, a] = rgba[1].split(",").map((s) => s.trim());
    if (r === undefined || g === undefined || b === undefined) {
      throw new Error(`malformed colour channel: ${value}`);
    }
    return [Number(r), Number(g), Number(b), a === undefined ? 1 : Number(a)];
  }
  throw new Error(`cannot parse colour: ${value}`);
}

/** Composite `top` (which may have alpha) over `bottom`. */
function over(
  top: [number, number, number, number],
  bottom: [number, number, number],
): [number, number, number] {
  const a = top[3];
  return [
    Math.round(top[0] * a + bottom[0] * (1 - a)),
    Math.round(top[1] * a + bottom[1] * (1 - a)),
    Math.round(top[2] * a + bottom[2] * (1 - a)),
  ];
}

function luminance([r, g, b]: [number, number, number]): number {
  const channel = (v: number): number => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrast(a: [number, number, number], b: [number, number, number]): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const bg0 = parseColour(token("--bg-0"));
const bg1 = parseColour(token("--bg-1"));
const glass = parseColour(token("--glass-fill"));
const glassStrong = parseColour(token("--glass-fill-strong"));

/** Effective surfaces: glass sits over the canvas. */
const surfaces: [string, [number, number, number]][] = [
  ["--bg-0", [bg0[0], bg0[1], bg0[2]]],
  ["--bg-1", [bg1[0], bg1[1], bg1[2]]],
  ["glass tile", over(glass, [bg0[0], bg0[1], bg0[2]])],
  ["strong glass", over(glassStrong, [bg0[0], bg0[1], bg0[2]])],
];

describe("token contrast (WCAG 2.2)", () => {
  it("parses the tokens it needs", () => {
    expect(css).toContain("--text-1:");
    expect(css).toContain("--harmonized-text:");
    expect(surfaces.length).toBe(4);
  });

  // text-3 is only used for non-essential labels, but it still has to clear AA.
  const textTokens = ["--text-1", "--text-2", "--text-3", "--harmonized-text"];

  for (const name of textTokens) {
    for (const [surfaceName, surface] of surfaces) {
      it(`${name} on ${surfaceName} meets AA`, () => {
        const colour = parseColour(token(name));
        expect(contrast([colour[0], colour[1], colour[2]], surface)).toBeGreaterThanOrEqual(4.5);
      });
    }
  }

  // The reading colours additionally carry AAA.
  for (const name of ["--text-1", "--text-2"]) {
    it(`${name} on the canvas meets AAA`, () => {
      const colour = parseColour(token(name));
      expect(
        contrast([colour[0], colour[1], colour[2]], [bg0[0], bg0[1], bg0[2]]),
      ).toBeGreaterThanOrEqual(7);
    });
  }

  // Toggle labels sit on a filled chip: ink on each fill.
  it("toggle ink is readable on both mode fills", () => {
    const ink = parseColour(token("--raw-ink"));
    const raw = parseColour(token("--raw"));
    const harm = parseColour(token("--harmonized"));
    expect(contrast([ink[0], ink[1], ink[2]], [raw[0], raw[1], raw[2]])).toBeGreaterThanOrEqual(
      4.5,
    );
    expect(contrast([ink[0], ink[1], ink[2]], [harm[0], harm[1], harm[2]])).toBeGreaterThanOrEqual(
      4.5,
    );
  });

  // Non-text UI components (focus ring, borders) need 3:1.
  it("the focus ring stands out from the canvas", () => {
    const ring = parseColour(token("--harmonized"));
    expect(contrast([ring[0], ring[1], ring[2]], [bg0[0], bg0[1], bg0[2]])).toBeGreaterThanOrEqual(
      3,
    );
  });

  it("keeps one accent family: no stray hue tokens", () => {
    // The direction is a single neon-green accent over neutral greens. If a
    // red, blue or purple accent sneaks into the token sheet, this fails.
    const accents = ["--harmonized", "--harmonized-text", "--raw", "--raw-ink"];
    for (const name of accents) {
      const [r, g, b] = parseColour(token(name));
      const isGreenish = g >= r && g >= b;
      expect(isGreenish, `${name} should sit in the green family`).toBe(true);
    }
  });
});
