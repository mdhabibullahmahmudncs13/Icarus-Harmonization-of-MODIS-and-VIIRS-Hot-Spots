import type { MetaBlock, Mode } from '../contract/types';
import type { View } from '../state/urlState';
import { ModeToggle } from './ModeToggle';
import { StatusCard } from './shared';

const VIEW_ITEMS: { id: View; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'calendar', label: 'Calendar' },
  { id: 'map', label: 'Map' },
  { id: 'anomalies', label: 'Anomalies' },
  { id: 'critical', label: 'Critical period' },
  { id: 'validation', label: 'Validation' },
];

const REF_ITEMS: { id: View; label: string }[] = [
  { id: 'methods', label: 'Methods' },
  { id: 'offline', label: 'Offline' },
];

export function Rail({
  view,
  mode,
  theme,
  meta,
  collapsed,
  onView,
  onMode,
  onTheme,
  onCollapse,
}: {
  view: View;
  mode: Mode;
  theme: 'dark' | 'light';
  meta: MetaBlock | null;
  collapsed: boolean;
  onView: (v: View) => void;
  onMode: (m: Mode) => void;
  onTheme: (t: 'dark' | 'light') => void;
  onCollapse: () => void;
}) {
  const all = [...VIEW_ITEMS, ...REF_ITEMS];
  return (
    <nav className={`rail${collapsed ? ' is-collapsed' : ''}`} aria-label="Primary">
      <div className="brand">
        <span className="brand__tile" aria-hidden="true">
          i
        </span>
        {!collapsed && (
          <span>
            <span className="brand__name">Icarus</span>
            <br />
            <span className="brand__sub">MODIS + VIIRS</span>
          </span>
        )}
        <button
          type="button"
          className="nav-item rail__collapse"
          onClick={onCollapse}
          aria-label="Collapse rail"
          title="Collapse (Ctrl/Cmd+B)"
        >
          {collapsed ? '»' : '«'}
        </button>
      </div>

      <ModeToggle mode={mode} onChange={onMode} />

      <div>
        <p className="nav-group__label">Views</p>
        {VIEW_ITEMS.map((item, i) => (
          <button
            key={item.id}
            type="button"
            className="nav-item"
            aria-current={view === item.id}
            onClick={() => onView(item.id)}
          >
            <span>{item.label}</span>
            <span className="nav-item__key">{i + 1}</span>
          </button>
        ))}
      </div>

      <div>
        <p className="nav-group__label">Reference</p>
        {REF_ITEMS.map((item, i) => (
          <button
            key={item.id}
            type="button"
            className="nav-item"
            aria-current={view === item.id}
            onClick={() => onView(item.id)}
          >
            <span>{item.label}</span>
            <span className="nav-item__key">{VIEW_ITEMS.length + i + 1}</span>
          </button>
        ))}
      </div>

      <button
        type="button"
        className="nav-item"
        onClick={() => onTheme(theme === 'dark' ? 'light' : 'dark')}
        aria-label="Toggle theme"
        title="Theme (T)"
      >
        <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
        <span className="nav-item__key">T</span>
      </button>

      {!collapsed && meta ? <StatusCard meta={meta} /> : null}
      <span hidden>{all.length}</span>
    </nav>
  );
}
