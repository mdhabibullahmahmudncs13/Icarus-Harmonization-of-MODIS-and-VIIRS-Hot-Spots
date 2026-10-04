/**
 * ApiDataSource — the real HTTP API (`src/api`, Phase 4).
 *
 * Same interface as MockDataSource, so `VITE_DATA=api` is the only change a
 * component ever sees (Implementation plan, Phase 5). Requests go to `/api/*`
 * on the app's own origin; the dev and preview servers proxy that prefix to
 * the local API (see `vite.config.ts`), so the browser makes no cross-origin
 * call and never contacts a third party. Set `VITE_API_BASE` only when the
 * API is served from a different origin (for example a container).
 *
 * Every response is validated against the zod contract at load time, exactly
 * as in mock mode, so a shape mismatch fails loudly instead of rendering
 * wrong numbers. The frontend never computes a statistic from a payload.
 */
import { endpoints, type EndpointName, type EndpointPayloads } from "../contract";
import type { DataSource } from "./DataSource";
import type {
  AnomalyResponse,
  BaselineResponse,
  CellsResponse,
  MetaResponse,
  MethodsResponse,
  SeriesResponse,
  ValidationResponse,
  Bbox,
} from "../contract";

/** Query values are strings; `undefined` and empty strings are dropped. */
type Query = Record<string, string | undefined>;

function buildUrl(path: string, params?: Query): string {
  const base = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== "") query.set(key, value);
  }
  const suffix = query.toString() === "" ? "" : `?${query.toString()}`;
  return `${base}/api/${path}${suffix}`;
}

/** The API reports failures as `{ "detail": "..." }`; fall back to text. */
async function readDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body !== null && typeof body === "object" && "detail" in body) {
      return String((body as { detail: unknown }).detail);
    }
  } catch {
    // Not JSON; fall through to a plain read.
  }
  try {
    return (await response.text()).slice(0, 200);
  } catch {
    return "";
  }
}

export class ApiDataSource implements DataSource {
  private async request<K extends EndpointName>(
    name: K,
    path: string,
    params?: Query,
  ): Promise<EndpointPayloads[K]> {
    const url = buildUrl(path, params);
    let response: Response;
    try {
      response = await fetch(url, { headers: { accept: "application/json" } });
    } catch (err) {
      throw new Error(
        `Could not reach the API at ${url}: ${String(err)}. Is the API running (make demo)?`,
        { cause: err },
      );
    }
    if (!response.ok) {
      const detail = await readDetail(response);
      throw new Error(
        `GET ${url} failed with HTTP ${response.status}${detail === "" ? "" : `: ${detail}`}`,
      );
    }
    let json: unknown;
    try {
      json = await response.json();
    } catch (err) {
      throw new Error(`Could not parse ${url} as JSON: ${String(err)}`, { cause: err });
    }
    const parsed = endpoints[name].safeParse(json);
    if (!parsed.success) {
      const detail = parsed.error.issues
        .slice(0, 3)
        .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
        .join("; ");
      throw new Error(`${url} does not satisfy the contract: ${detail}`);
    }
    return parsed.data as EndpointPayloads[K];
  }

  getMeta(): Promise<MetaResponse> {
    return this.request("meta", "meta");
  }

  getSeries(): Promise<SeriesResponse> {
    return this.request("series", "series");
  }

  getCells(start?: string, end?: string): Promise<CellsResponse> {
    return this.request("cells", "cells", { start, end });
  }

  getBaseline(): Promise<BaselineResponse> {
    return this.request("baseline", "baseline");
  }

  getAnomaly(date: string, bbox?: Bbox): Promise<AnomalyResponse> {
    return this.request("anomaly", "anomaly", {
      date,
      bbox: bbox === undefined ? undefined : bbox.join(","),
    });
  }

  getValidation(): Promise<ValidationResponse> {
    return this.request("validation", "validation");
  }

  getMethods(): Promise<MethodsResponse> {
    return this.request("methods", "methods");
  }
}
