export type IconName =
  | 'overview'
  | 'calendar'
  | 'map'
  | 'anomalies'
  | 'critical'
  | 'validation'
  | 'methods'
  | 'offline'
  | 'sun'
  | 'moon'
  | 'fingerprint'
  | 'help'
  | 'close'
  | 'chevron-left'
  | 'chevron-right'
  | 'area';

const PATHS: Record<IconName, string> = {
  overview: 'M4 13h6V4H4v9Zm0 7h6v-4H4v4Zm10 0h6v-9h-6v9Zm0-16v4h6V4h-6Z',
  calendar:
    'M7 3v3M17 3v3M4 9h16M5 6h14a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z',
  map: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Zm0 0v14m6-12v14',
  anomalies: 'M3 15h4l3-9 4 13 3-8h4',
  critical: 'M12 3s5 4.5 5 9a5 5 0 0 1-10 0c0-2 1-3.5 2-4.5 0 1.5.8 2.5 2 2.5 1.2 0 2-1 2-2.5 0-1.5-1-3.5-1-4.5Z',
  validation: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-3.5-9.2 2.4 2.4 4.6-5',
  methods: 'M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4Zm0 0a2 2 0 0 0-2 2v11m14 1h2a2 2 0 0 0 2-2V6',
  offline: 'M12 4v10m0 0 4-4m-4 4-4-4M5 18h14',
  sun: 'M12 7.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9ZM12 2v2m0 16v2M4.2 4.2l1.5 1.5m12.6 12.6 1.5 1.5M2 12h2m16 0h2M4.2 19.8l1.5-1.5M18.3 5.7l1.5-1.5',
  moon: 'M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z',
  fingerprint:
    'M12 11a2 2 0 0 0-2 2c0 2.5.5 4.5 1.3 6M8 8.5A6 6 0 0 1 18 13c0 1.6-.1 3-.5 4.5M5.5 12A6.5 6.5 0 0 1 12 5.5c1.6 0 3 .6 4.2 1.6M4 16.5c.6-1 .9-2.2 1-3.5m4.7 6.5c1-1.8 1.6-4.2 1.8-7a4 4 0 0 1 7.6 1.6',
  help: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-3.6c0-1.6-2-2.4-2-4m2-6.2h.01',
  close: 'm6 6 12 12M18 6 6 18',
  'chevron-left': 'm14 6-6 6 6 6',
  'chevron-right': 'm10 6 6 6-6 6',
  area: 'M4 6h6v6H4V6Zm10 0h6v6h-6V6ZM4 15h6v4H4v-4Zm10 0h6v4h-6v-4Z',
};

export function Icon({ name, size = 17 }: { name: IconName; size?: number }) {
  return (
    <svg
      className="nav-item__icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
