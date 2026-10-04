/**
 * ApiDataSource — the real HTTP API (Phase 4, not implemented yet).
 *
 * Kept here so the data layer is already wired for the swap from mock to
 * real data: switching `VITE_DATA=api` is the only change (plan, Phase 5).
 */
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

export class ApiDataSource implements DataSource {
  private notImplemented(): never {
    throw new Error("not implemented");
  }

  getMeta(): Promise<MetaResponse> {
    this.notImplemented();
  }

  getSeries(): Promise<SeriesResponse> {
    this.notImplemented();
  }

  getCells(_start?: string, _end?: string): Promise<CellsResponse> {
    this.notImplemented();
  }

  getBaseline(): Promise<BaselineResponse> {
    this.notImplemented();
  }

  getAnomaly(_date: string, _bbox?: Bbox): Promise<AnomalyResponse> {
    this.notImplemented();
  }

  getValidation(): Promise<ValidationResponse> {
    this.notImplemented();
  }

  getMethods(): Promise<MethodsResponse> {
    this.notImplemented();
  }
}
