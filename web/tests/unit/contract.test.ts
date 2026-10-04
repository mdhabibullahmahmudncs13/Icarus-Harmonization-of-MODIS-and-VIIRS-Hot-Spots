/**
 * Contract tests: every generated mock file must satisfy its zod schema,
 * and malformed payloads must be rejected. The same schemas export to
 * docs/contract.schema.json for the Python contract tests.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { endpoints, type EndpointName } from "../../src/contract/schemas";

function loadMock(name: EndpointName): unknown {
  const file = resolve(process.cwd(), "public/mock", `${name}.json`);
  return JSON.parse(readFileSync(file, "utf8")) as unknown;
}

describe("generated mock files satisfy the contract", () => {
  for (const name of Object.keys(endpoints) as EndpointName[]) {
    it(`${name}.json parses against the ${name} schema`, () => {
      const payload = loadMock(name);
      const result = endpoints[name].safeParse(payload);
      expect(result.success).toBe(true);
    });
  }
});

describe("malformed payloads are rejected", () => {
  it("accepts the unmodified series payload as a baseline", () => {
    const payload = loadMock("series");
    expect(endpoints.series.safeParse(payload).success).toBe(true);
  });

  it("rejects a series row with a missing field", () => {
    const payload = loadMock("series") as { rows: Record<string, unknown>[] };
    delete payload.rows[0].raw_total;
    expect(endpoints.series.safeParse(payload).success).toBe(false);
  });

  it("rejects a series row with a non-integer count", () => {
    const payload = loadMock("series") as { rows: Record<string, unknown>[] };
    payload.rows[0].raw_total = 1.5;
    expect(endpoints.series.safeParse(payload).success).toBe(false);
  });

  it("rejects a series row with a malformed date", () => {
    const payload = loadMock("series") as { rows: Record<string, unknown>[] };
    payload.rows[0].date = "01/01/2003";
    expect(endpoints.series.safeParse(payload).success).toBe(false);
  });

  it("rejects an unknown meta.source", () => {
    const payload = loadMock("meta") as { meta: Record<string, unknown> };
    payload.meta.source = "alien";
    expect(endpoints.meta.safeParse(payload).success).toBe(false);
  });

  it("rejects a bbox that is not four numbers", () => {
    const payload = loadMock("meta") as { meta: { region: Record<string, unknown> } };
    payload.meta.region.bbox = [88, 20, 93];
    expect(endpoints.meta.safeParse(payload).success).toBe(false);
  });

  it("rejects a cell with bounds of the wrong length", () => {
    const payload = loadMock("cells") as { rows: Record<string, unknown>[] };
    payload.rows[0].bounds = [88, 20, 93];
    expect(endpoints.cells.safeParse(payload).success).toBe(false);
  });

  it("rejects a negative peak_frp", () => {
    const payload = loadMock("cells") as { rows: Record<string, unknown>[] };
    payload.rows[0].peak_frp = -1;
    expect(endpoints.cells.safeParse(payload).success).toBe(false);
  });

  it("rejects a baseline percentile above the observable range", () => {
    const payload = loadMock("baseline") as { rows: Record<string, unknown>[] };
    payload.rows[0].p95 = -3;
    expect(endpoints.baseline.safeParse(payload).success).toBe(false);
  });

  it("rejects an anomaly percentile outside 0-100", () => {
    const payload = loadMock("anomaly") as { percentile: number };
    payload.percentile = 150;
    expect(endpoints.anomaly.safeParse(payload).success).toBe(false);
  });

  it("rejects a correlation outside -1..1", () => {
    const payload = loadMock("validation") as { raw: Record<string, unknown> };
    payload.raw.pearson = 2;
    expect(endpoints.validation.safeParse(payload).success).toBe(false);
  });

  it("rejects methods without a collapse rule", () => {
    const payload = loadMock("methods") as Record<string, unknown>;
    delete payload.collapse_rule;
    expect(endpoints.methods.safeParse(payload).success).toBe(false);
  });

  it("rejects a response with no meta block", () => {
    const payload = loadMock("series") as Record<string, unknown>;
    delete payload.meta;
    expect(endpoints.series.safeParse(payload).success).toBe(false);
  });
});
