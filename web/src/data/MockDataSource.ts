/**
 * MockDataSource — reads the generated JSON files from `public/mock/`.
 *
 * Every payload is validated against the zod contract at load time, so a
 * shape mismatch fails loudly instead of rendering wrong numbers.
 * Mock data is never evidence: the UI shows the persistent MockBanner
 * whenever `meta.source` is "mock".
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

export class MockDataSource implements DataSource {
  private async load<K extends EndpointName>(name: K): Promise<EndpointPayloads[K]> {
    const url = `/mock/${name}.json`;
    let response: Response;
    try {
      response = await fetch(url);
    } catch (err) {
      throw new Error(`Could not fetch ${url}: ${String(err)}. Run \`npm run mock:gen\`.`, {
        cause: err,
      });
    }
    if (!response.ok) {
      throw new Error(`Could not fetch ${url}: HTTP ${response.status}. Run \`npm run mock:gen\`.`);
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
        .map((i) => `${i.path.join(".")}: ${i.message}`)
        .join("; ");
      throw new Error(`${url} does not satisfy the contract: ${detail}`);
    }
    return parsed.data as EndpointPayloads[K];
  }

  getMeta(): Promise<MetaResponse> {
    return this.load("meta");
  }

  getSeries(): Promise<SeriesResponse> {
    return this.load("series");
  }

  // The mock file covers the full date range; the window parameters are
  // accepted to match the interface but are not applied in mock mode.
  getCells(_start?: string, _end?: string): Promise<CellsResponse> {
    return this.load("cells");
  }

  getBaseline(): Promise<BaselineResponse> {
    return this.load("baseline");
  }

  // The mock file contains one fixed sample date; date/bbox are accepted to
  // match the interface but are not applied in mock mode.
  getAnomaly(_date: string, _bbox?: Bbox): Promise<AnomalyResponse> {
    return this.load("anomaly");
  }

  getValidation(): Promise<ValidationResponse> {
    return this.load("validation");
  }

  getMethods(): Promise<MethodsResponse> {
    return this.load("methods");
  }
}
