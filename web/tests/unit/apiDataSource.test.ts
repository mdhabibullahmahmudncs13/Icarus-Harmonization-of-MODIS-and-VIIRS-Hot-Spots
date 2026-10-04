/**
 * ApiDataSource tests.
 *
 * `fetch` is stubbed, so these run offline and assert the two things the data
 * layer must guarantee: the request path the API expects, and that a response
 * is validated against the same zod contract the mock files use before any
 * component sees it.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiDataSource } from "../../src/data/ApiDataSource";
import type { EndpointName } from "../../src/contract";

function loadMock(name: EndpointName): unknown {
  const file = resolve(process.cwd(), "public/mock", `${name}.json`);
  return JSON.parse(readFileSync(file, "utf8")) as unknown;
}

function reply(body: unknown, init: { ok?: boolean; status?: number } = {}): Response {
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

function stubFetch(response: Response | (() => Promise<never>)): ReturnType<typeof vi.fn> {
  const mock = typeof response === "function" ? vi.fn(response) : vi.fn(async () => response);
  vi.stubGlobal("fetch", mock);
  return mock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("request paths", () => {
  it("asks for each endpoint on its contract path", async () => {
    const fetchMock = stubFetch(reply(loadMock("meta")));
    await new ApiDataSource().getMeta();
    expect(fetchMock).toHaveBeenCalledWith("/api/meta", expect.anything());
  });

  it("sends no query string when there are no parameters", async () => {
    const fetchMock = stubFetch(reply(loadMock("cells")));
    await new ApiDataSource().getCells();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/cells");
  });

  it("passes the cells window as start and end", async () => {
    const fetchMock = stubFetch(reply(loadMock("cells")));
    await new ApiDataSource().getCells("2019-02-01", "2019-02-28");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/cells?start=2019-02-01&end=2019-02-28");
  });

  it("passes the anomaly date", async () => {
    const fetchMock = stubFetch(reply(loadMock("anomaly")));
    await new ApiDataSource().getAnomaly("2019-06-01");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/anomaly?date=2019-06-01");
  });

  it("joins a bbox into the comma-separated query form", async () => {
    const fetchMock = stubFetch(reply(loadMock("anomaly")));
    await new ApiDataSource().getAnomaly("2019-06-01", [88, 20, 93, 27]);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/anomaly?date=2019-06-01&bbox=88%2C20%2C93%2C27");
  });
});

describe("contract validation", () => {
  it("resolves a payload that satisfies the contract", async () => {
    stubFetch(reply(loadMock("series")));
    const payload = await new ApiDataSource().getSeries();
    expect(payload.rows.length).toBeGreaterThan(0);
    expect(payload.rows[0]).toHaveProperty("raw_total");
  });

  it("rejects a payload that does not satisfy the contract", async () => {
    const broken = loadMock("meta") as { sensors?: unknown };
    delete broken.sensors;
    stubFetch(reply(broken));
    await expect(new ApiDataSource().getMeta()).rejects.toThrow(/does not satisfy the contract/);
  });
});

describe("failures", () => {
  it("reports the HTTP status and the API's detail", async () => {
    stubFetch(
      reply({ detail: "2019-01-01 is outside the dataset range" }, { ok: false, status: 404 }),
    );
    await expect(new ApiDataSource().getAnomaly("1999-01-01")).rejects.toThrow(
      /HTTP 404: 2019-01-01 is outside the dataset range/,
    );
  });

  it("explains an unreachable API instead of leaking the fetch error", async () => {
    stubFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    await expect(new ApiDataSource().getMeta()).rejects.toThrow(/Could not reach the API/);
  });
});
