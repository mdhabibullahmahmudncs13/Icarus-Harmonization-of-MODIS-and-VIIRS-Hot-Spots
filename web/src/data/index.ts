/**
 * Data layer entry point: the active source is selected by VITE_DATA
 * (`mock` | `api`, default `mock`). Components only ever see DataSource.
 */
import type { DataSource } from "./DataSource";
import { MockDataSource } from "./MockDataSource";
import { ApiDataSource } from "./ApiDataSource";

export type { DataSource } from "./DataSource";
export { MockDataSource } from "./MockDataSource";
export { ApiDataSource } from "./ApiDataSource";

export function createDataSource(): DataSource {
  const which = import.meta.env.VITE_DATA ?? "mock";
  return which === "api" ? new ApiDataSource() : new MockDataSource();
}
