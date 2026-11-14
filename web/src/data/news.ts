import type { FireNewsPayload } from '../contract/types';

/** A failed news request, carrying the API's contract error code when it has one. */
export class FireNewsRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | null,
  ) {
    super(message);
    this.name = 'FireNewsRequestError';
  }
}

/**
 * The endpoint the agent lives on.
 *
 * `VITE_API_BASE` points at the versioned API (`/api/v1`); the news route is
 * unversioned, so the version suffix is removed rather than duplicated. With
 * no base configured the relative path is used, which the Vite dev server
 * proxies to the local API.
 */
export function newsEndpoint(): string {
  const configured = import.meta.env.VITE_API_BASE ?? '';
  const root = configured.replace(/\/v1\/?$/, '').replace(/\/$/, '');
  return `${root}/api/fire-news`;
}

interface FireNewsQuery {
  date: string;
  region: string;
  refresh?: boolean;
  signal?: AbortSignal;
}

/** Ask the backend agent for sourced fire news on one day in one region. */
export async function fetchFireNews({
  date,
  region,
  refresh = false,
  signal,
}: FireNewsQuery): Promise<FireNewsPayload> {
  const url = newsEndpoint();
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, region, refresh }),
    signal,
  });

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new FireNewsRequestError(
      `POST ${url} did not return JSON (HTTP ${response.status}). Start the API and set VITE_API_BASE.`,
      response.status,
      null,
    );
  }

  if (!response.ok) {
    const error = (body ?? {}) as { message?: string; code?: string };
    throw new FireNewsRequestError(
      error.message ?? `POST ${url} failed with HTTP ${response.status}`,
      response.status,
      error.code ?? null,
    );
  }
  return body as FireNewsPayload;
}
