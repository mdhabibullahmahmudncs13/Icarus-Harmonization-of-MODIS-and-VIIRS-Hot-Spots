/**
 * The single data interface every component talks to.
 *
 * Components never know whether data comes from mock files or the API;
 * they only see this interface (Implementation plan, section 5.2).
 */
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

export interface DataSource {
  /** Region, parameters, sensor epochs. */
  getMeta(): Promise<MetaResponse>;
  /** Daily counts — one fetch feeds every chart. */
  getSeries(): Promise<SeriesResponse>;
  /** Grid cells for the map over a window (optional, loads lazily). */
  getCells(start?: string, end?: string): Promise<CellsResponse>;
  /** Seasonal baseline. */
  getBaseline(): Promise<BaselineResponse>;
  /** "Is this unusual?" */
  getAnomaly(date: string, bbox?: Bbox): Promise<AnomalyResponse>;
  /** Overlap-period validation. */
  getValidation(): Promise<ValidationResponse>;
  /** Methods panel content. */
  getMethods(): Promise<MethodsResponse>;
}
