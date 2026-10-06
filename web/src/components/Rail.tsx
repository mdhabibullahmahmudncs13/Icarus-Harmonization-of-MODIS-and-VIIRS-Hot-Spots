import type { MetaBlock, Mode } from '../contract/types';
import type { View } from '../state/urlState';
import { Icon, type IconName } from './Icon';
import { ModeToggle } from './ModeToggle';
import { StatusCard } from './shared';

const VIEW_ITEMS: { id: View; label: string; icon: IconName }[] = [
  { id: 'overview', label: 'Overview', icon: 'overview' },
  { id: 'calendar', label: 'Calendar', icon: 'calendar' },
  { id: 'map', label: 'Map', icon: 'map' },
  { id: 'anomalies', label: 'Anomalies', icon: 'anomalies' },
  { id: 'critical', label: 'Critical period', icon: 'critical' },
  { id: 'validation', label: 'Validation', icon: 'validation' },
];

const REF_ITEMS: { id: View; label: string; icon: IconName }[] = [
  { id: 'methods', label: 'Methods', icon: 'methods' },
  { id: 'offline', label: 'Offline', icon: 'offline' },
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
  const item = (entry: { id: View; label: string; icon: IconName }, index: number) => (
    <button
      key={entry.id}
      type="button"
      className="nav-item"
      aria-current={view === entry.id ? 'page' : undefined}
      aria-label={collapsed ? entry.label : undefined}
      title={collapsed ? `${entry.label} (${index})` : undefined}
      onClick={() => onView(entry.id)}
    >
      <Icon name={entry.icon} />
      <span className="nav-item__label">{entry.label}</span>
      <span className="nav-item__key">{index}</span>
    </button>
  );

  return (
    <nav className={`rail${collapsed ? ' is-collapsed' : ''}`} aria-label="Primary">
      <div className="brand">
        <span className="brand__tile" aria-hidden="true">
          i
        </span>
        <span className="brand__meta">
          <span className="brand__name">Icarus</span>
          <span className="brand__sub">MODIS + VIIRS hot spots</span>
        </span>
        <button
          type="button"
          className="rail__collapse"
          onClick={onCollapse}
          aria-label={collapsed ? 'Expand rail' : 'Collapse rail'}
          aria-expanded={!collapsed}
          title="Collapse (Ctrl/Cmd+B)"
        >
          <Icon name={collapsed ? 'chevron-right' : 'chevron-left'} size={16} />
        </button>
      </div>

      <ModeToggle mode={mode} onChange={onMode} compact={collapsed} />

      <div className="rail__nav">
        <div className="nav-group">
          <p className="nav-group__label">Views</p>
          {VIEW_ITEMS.map((entry, i) => item(entry, i + 1))}
        </div>
        <div className="nav-group">
          <p className="nav-group__label">Reference</p>
          {REF_ITEMS.map((entry, i) => item(entry, VIEW_ITEMS.length + i + 1))}
        </div>
      </div>

      <button
        type="button"
        className="nav-item rail__theme"
        onClick={() => onTheme(theme === 'dark' ? 'light' : 'dark')}
        aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        title="Theme (T)"
      >
        <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
        <span className="nav-item__label">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
        <span className="nav-item__key">T</span>
      </button>

      {!collapsed && meta ? <StatusCard meta={meta} /> : null}
    </nav>
  );
}
