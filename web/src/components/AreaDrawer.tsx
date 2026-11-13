import { Icon } from './Icon';
import { describeRing, isUsableRing, type Ring } from '../lib/polygon';

/**
 * The controls for drawing a custom area (FR-16).
 *
 * The map takes the clicks; this says what the user is doing and what they
 * can do next. The shape is only applied once it is usable — three points,
 * not flat, not crossing itself — because the API refuses anything else and
 * a refusal after the fact is worse than a disabled button.
 */
export function AreaDrawer({
  ring,
  drawing,
  onStart,
  onCancel,
  onClear,
  onFinish,
}: {
  /** The shape being drawn, or the one already applied. */
  ring: Ring | null;
  /** Is the user drawing right now? */
  drawing: boolean;
  onStart: () => void;
  onCancel: () => void;
  onClear: () => void;
  onFinish: (ring: Ring) => void;
}) {
  const points = ring?.length ?? 0;
  const usable = ring !== null && isUsableRing(ring);

  if (!drawing && !ring) {
    return (
      <button type="button" className="btn" onClick={onStart}>
        <Icon name="area" size={16} />
        Draw an area
      </button>
    );
  }

  if (drawing) {
    return (
      <div className="area-drawer" role="group" aria-label="Draw an area">
        <span className="area-drawer__count">
          {points} {points === 1 ? 'point' : 'points'} — click the map to add more
        </span>
        <button
          type="button"
          className="btn btn--primary"
          disabled={!usable}
          onClick={() => ring && onFinish(ring)}
          title={usable ? 'Apply this area' : 'A shape needs three points and must not cross itself'}
        >
          Use this area
        </button>
        <button type="button" className="btn btn--quiet" onClick={onCancel}>
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="area-drawer" role="group" aria-label="Custom area">
      <span className="area-drawer__count" title="The drawn area">
        {describeRing(ring)}
      </span>
      <button type="button" className="btn" onClick={onStart}>
        <Icon name="area" size={16} />
        Redraw
      </button>
      <button type="button" className="btn btn--quiet" onClick={onClear}>
        Clear
      </button>
    </div>
  );
}
