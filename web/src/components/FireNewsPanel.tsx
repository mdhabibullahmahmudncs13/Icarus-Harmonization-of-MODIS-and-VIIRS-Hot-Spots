import { useCallback, useEffect, useRef, useState } from 'react';

import type { FireNewsPayload } from '../contract/types';
import { fetchFireNews } from '../data/news';
import { Icon } from './Icon';

const SATELLITE_LABEL: Record<FireNewsPayload['results'][number]['satellite_agreement'], string> = {
  agrees: 'Satellite detections this day',
  no_detections: 'No satellite detections',
  unavailable: 'Satellite check unavailable',
};

/**
 * The fire-news view: one date, one region, sourced reports or an honest empty state.
 *
 * The request is made when this view is opened and whenever its date or region
 * changes. The backend caches per (date, region), so returning to the same pair
 * does not repeat the search; "Search again" asks it to bypass that cache.
 */
export function FireNewsPanel({
  date,
  regionId,
  regionLabel,
  onDate,
}: {
  date: string | null;
  regionId: string;
  regionLabel: string;
  onDate: (date: string) => void;
}) {
  const [payload, setPayload] = useState<FireNewsPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const requestId = useRef(0);

  const run = useCallback(
    async (refresh: boolean) => {
      if (!date) return;
      const id = ++requestId.current;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      let timedOut = false;
      const timer = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, 45_000);

      setLoading(true);
      setError(null);
      try {
        const next = await fetchFireNews({
          date,
          region: regionId,
          refresh,
          signal: controller.signal,
        });
        if (id === requestId.current) {
          setPayload(next);
          setError(null);
        }
      } catch (cause) {
        if (id !== requestId.current) return;
        setError(
          timedOut
            ? 'The news search took too long. Try again, or pick a different day.'
            : cause instanceof Error
              ? cause.message
              : String(cause),
        );
      } finally {
        clearTimeout(timer);
        if (id === requestId.current) setLoading(false);
      }
    },
    [date, regionId],
  );

  useEffect(() => {
    setPayload(null);
    void run(false);
    return () => abortRef.current?.abort();
  }, [run]);

  if (!date) {
    return (
      <div className="card">
        <div className="card__head">
          <span className="card__title">Fire news</span>
        </div>
        <div className="card__body">
          <p className="empty">Pick a day to search for fire reports in {regionLabel}.</p>
        </div>
      </div>
    );
  }

  const satellite = payload?.satellite;
  const hasResults = Boolean(payload && payload.results.length > 0);
  return (
    <div className="card">
      <div className="card__head">
        <span className="card__title">Fire news</span>
        <span className="badge badge--outline">{regionLabel}</span>
        {payload?.cached ? <span className="badge badge--neutral">cached</span> : null}
      </div>
      <div className="card__body">
        <div className="news-controls">
          <label className="news-date">
            <span className="news-date__label">Day</span>
            <input
              className="news-date__input"
              type="date"
              value={date}
              onChange={(event) => event.target.value && onDate(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="btn btn--quiet"
            onClick={() => void run(true)}
            disabled={loading}
            title="Search again, bypassing the cached result"
          >
            <Icon name="refresh" size={15} />
            Search again
          </button>
          <span className="news-controls__note">
            Hyperbrowser searches the web; only articles matching this day and region are kept.
          </span>
        </div>

        {loading ? (
          <p className="news-status" role="status" aria-live="polite">
            Searching the web for {regionLabel} on {date}…
          </p>
        ) : null}

        {error ? (
          <div className="error" role="alert">
            <strong>Could not search fire news</strong>
            <span>{error}</span>
            <span>
              <button type="button" className="btn btn--primary" onClick={() => void run(false)}>
                Try again
              </button>
            </span>
          </div>
        ) : null}

        {!loading && !error && payload ? (
          <>
            {satellite?.available ? (
              <p className="news-satellite">
                Satellite cross-check:{' '}
                <b>{satellite.detections}</b> detections in{' '}
                <b>{satellite.active_cells}</b> cells on this day.{' '}
                {hasResults
                  ? satellite.agrees_with_news
                    ? 'News and detections agree.'
                    : 'No satellite detections back up these reports.'
                  : satellite.detections > 0
                    ? 'Detections exist, but no sourced news report matched.'
                    : 'No detections either.'}
              </p>
            ) : (
              <p className="news-satellite">
                Satellite cross-check unavailable for this region and day.
              </p>
            )}

            {hasResults ? (
              <ul className="news-list">
                {payload.results.map((item) => (
                  <li className="news-item" key={item.url}>
                    <a
                      className="news-item__headline"
                      href={item.url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      {item.headline} ↗
                    </a>
                    <p className="news-item__summary">{item.summary}</p>
                    <div className="news-item__meta">
                      <span className="news-item__source">{item.source_name}</span>
                      <time dateTime={item.published_date}>{item.published_date}</time>
                      <span className={`news-item__agree news-item__agree--${item.satellite_agreement}`}>
                        {SATELLITE_LABEL[item.satellite_agreement]}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty" role="status">
                {payload.message ??
                  `No fire reports found for ${regionLabel} on ${date}.`}
              </p>
            )}

            <p className="hint">
              {payload.partial ? 'Some pages could not be read before the time budget ran out. ' : ''}
              Every result links to its source. Nothing is generated when no article matches.
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}
