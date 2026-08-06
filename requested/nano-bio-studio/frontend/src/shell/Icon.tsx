/**
 * Line icon set.
 *
 * Inline SVG rather than an icon font or dependency: it keeps the bundle small,
 * inherits `currentColor`, and stays crisp at any size. All icons are
 * decorative — every navigation item also carries a visible or accessible text
 * label, so icons are marked `aria-hidden`.
 */

export type IconName =
  | 'grid' | 'hexagon' | 'play' | 'list' | 'compare' | 'flask' | 'atom'
  | 'sparkle' | 'folder' | 'clock' | 'document' | 'shield' | 'gear'
  | 'menu' | 'chevron-left' | 'chevron-right' | 'logout' | 'user' | 'close'
  | 'check' | 'arrow-right' | 'refresh' | 'edit' | 'info';

const PATHS: Record<IconName, string> = {
  grid: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
  hexagon: 'M12 3l7.5 4.33v8.66L12 20.32 4.5 15.99V7.33z M12 8.2l3.6 2.08v4.16L12 16.52l-3.6-2.08v-4.16z',
  play: 'M6 4.5v15l12-7.5z',
  list: 'M4 6h16M4 12h16M4 18h10',
  compare: 'M9 4v16M15 4v16M4 8l3-3 3 3M20 16l-3 3-3-3',
  flask: 'M9 3h6M10 3v6L5 19a2 2 0 0 0 1.8 2.9h10.4A2 2 0 0 0 19 19l-5-10V3M7.5 14h9',
  atom: 'M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0 M12 3c4.97 0 9 4.03 9 9s-4.03 9-9 9-9-4.03-9-9 4.03-9 9-9z M4.6 7.5c2.5-4.3 8.3-5.8 12.6-3.3s5.8 8.3 3.3 12.6',
  sparkle: 'M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4zM18 15l.9 2.4L21 18l-2.1.9L18 21l-.9-2.1L15 18l2.1-.6z',
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3.5 2',
  document: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h4',
  shield: 'M12 3l7.5 3v6c0 4.4-3.1 8.2-7.5 9.4C7.6 20.2 4.5 16.4 4.5 12V6zM9.3 12.2l2 2 3.4-3.6',
  gear: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1v.2a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-2.8-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3.5 15H3.3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 8.3l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 2.7-1.1V4.2a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.8 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7h.2a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z',
  menu: 'M4 7h16M4 12h16M4 17h16',
  'chevron-left': 'M15 5l-7 7 7 7',
  'chevron-right': 'M9 5l7 7-7 7',
  logout: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 16l-4-4 4-4M6 12h12',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM5 20a7 7 0 0 1 14 0',
  close: 'M6 6l12 12M18 6L6 18',
  check: 'M5 12.5l4.5 4.5L19 7',
  'arrow-right': 'M5 12h13M12 5l7 7-7 7',
  refresh: 'M20 11a8 8 0 1 0-2.3 6M20 5v6h-6',
  edit: 'M4 20h4L19 9a2 2 0 0 0-3-3L5 17zM15 6l3 3',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 7.6v.1',
};

export function Icon({
  name, size = 18, strokeWidth = 1.6, className = '',
}: { name: IconName; size?: number; strokeWidth?: number; className?: string }) {
  return (
    <svg
      className={`ns-icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

/** The NanoBio Studio mark: a nanoparticle core with an orbiting shell. */
export function BrandMark({ size = 30 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      aria-hidden="true"
      focusable="false"
      className="ns-brandmark"
    >
      <defs>
        <linearGradient id="nsBrandGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#35bcd8" />
          <stop offset="100%" stopColor="#0a6c82" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="40" height="40" rx="10" fill="url(#nsBrandGrad)" />
      <circle cx="20" cy="20" r="5.4" fill="#fff" fillOpacity="0.96" />
      <ellipse cx="20" cy="20" rx="12.5" ry="6.4" fill="none" stroke="#fff"
               strokeOpacity="0.72" strokeWidth="1.5" transform="rotate(-28 20 20)" />
      <ellipse cx="20" cy="20" rx="12.5" ry="6.4" fill="none" stroke="#fff"
               strokeOpacity="0.45" strokeWidth="1.5" transform="rotate(38 20 20)" />
      <circle cx="31.2" cy="13.6" r="2" fill="#fff" fillOpacity="0.9" />
    </svg>
  );
}
