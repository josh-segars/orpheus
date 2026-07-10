/**
 * Inline Material Design icons (ORPHEUS-105).
 *
 * Single source of truth for the app's glyph iconography, so every icon is a
 * box-aligned 24×24 SVG rather than a text character (✓/✕/←/→/‹/› etc.) whose
 * vertical metrics drift against adjacent text. Renders `currentColor`, so the
 * icon inherits the surrounding text color and hover states for free.
 *
 * Path data is the official Material Symbols outline set (24px grid). Add a
 * new entry to PATHS to expose another icon.
 *
 * The HTML prototype can't import this — it inlines the same <svg> markup
 * directly per the visual-source-of-truth contract.
 */
const PATHS = {
  check: 'M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.42z',
  close:
    'M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
  chevron_left: 'M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z',
  chevron_right: 'M10 6 8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z',
  arrow_back: 'M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20z',
  arrow_forward: 'M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z',
  // Filled triangle used for the sub-dimension expand/collapse caret
  // (Material `arrow_right`); rotated 90° via CSS when expanded.
  arrow_right: 'M10 17V7l5 5z',
} as const

export type MaterialIconName = keyof typeof PATHS

interface MaterialIconProps {
  name: MaterialIconName
  /** Rendered box size in px (width = height). Defaults to 18. */
  size?: number
  className?: string
}

export function MaterialIcon({ name, size = 18, className }: MaterialIconProps) {
  // Always carry the base class (for inline vertical-align); merge any caller
  // class. vertical-align is inert inside flex/inline-flex parents, so this is
  // safe everywhere the icon is used.
  const classes = className ? `material-icon ${className}` : 'material-icon'
  return (
    <svg
      className={classes}
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      width={size}
      height={size}
    >
      <path d={PATHS[name]} fill="currentColor" />
    </svg>
  )
}
