import { exportUrl, formatCount } from '../lib/export';
import type { Ring } from '../lib/polygon';
import { Icon } from './Icon';

/**
 * The CSV export button.
 *
 * The challenge asks for the hotspot records behind the view to be
 * downloadable, so the button is a link to the API's export route with the
 * area and window the view is showing. The browser does the download, so no
 * blob is built in JavaScript and no file is ever held in memory.
 *
 * The button says how many records it will fetch: the whole record for a
 * large area is tens of megabytes, and a download that size should be
 * something the user agreed to.
 */
export function ExportButton({
  base,
  aoi,
  polygon = null,
  start,
  end,
  count,
}: {
  /** The API's base address. */
  base: string;
  /** Preset id of the area to export. */
  aoi?: string;
  /** The drawn area, when there is one. It wins over the preset. */
  polygon?: Ring | null;
  /** First day of the window, `YYYY-MM-DD`. */
  start?: string | null;
  /** Last day of the window, `YYYY-MM-DD`. */
  end?: string | null;
  /** How many records the export will hold. */
  count: number;
}) {
  const href = exportUrl(base, { aoi, polygon, start, end });
  const window = start && end ? `${start} to ${end}` : 'the whole record';
  const size = formatCount(count);
  return (
    <a
      className="btn"
      href={href}
      download
      title={`Download ${size} for ${window}`}
    >
      <Icon name="download" size={16} />
      Export CSV
      <span className="btn__count">{size}</span>
    </a>
  );
}
