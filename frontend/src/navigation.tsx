export default function Navigation({ active }: { active: string }) {
  return (
    <nav className="bottom-nav" aria-label="Main navigation">
      {[
        ['briefing', 'Briefing', '◫'],
        ['research', 'Research', '↗'],
        ['portfolio', 'Portfolio', '◷'],
      ].map(([view, title, icon]) => (
        <a key={view} href={`/?view=${view}`} aria-current={active === view ? 'page' : undefined}>
          <span aria-hidden="true">{icon}</span>
          {title}
        </a>
      ))}
    </nav>
  )
}
