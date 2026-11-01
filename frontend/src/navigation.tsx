export type View = 'briefing' | 'research' | 'portfolio' | 'status'

export default function Navigation({
  active,
  placement,
  locations,
}: {
  active: View
  placement: 'desktop' | 'mobile'
  locations: Partial<Record<View, string>>
}) {
  return (
    <nav className={`app-navigation ${placement}-navigation`} aria-label="Main navigation">
      {[
        ['briefing', 'Briefing', 'M4 4h16v16H4zM8 8h8M8 12h8M8 16h4'],
        ['research', 'Research', 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM16 16l5 5'],
        ['portfolio', 'Portfolio', 'M4 8h16v12H4zM9 8V4h6v4M4 13h16M10 13v3h4v-3'],
      ].map(([view, title, path]) => (
        <a
          key={view}
          href={locations[view as View] || `/?view=${view}`}
          data-section={view}
          aria-current={active === view ? 'page' : undefined}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            aria-hidden="true"
          >
            <path d={path} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {title}
        </a>
      ))}
    </nav>
  )
}
