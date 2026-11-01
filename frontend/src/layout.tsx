import type { ReactNode } from 'react'
import Navigation, { type View } from './navigation'
import ThemeSelector from './theme'

export const PAGE_TITLES: Record<View, string> = {
  briefing: 'Your Briefing',
  research: 'Company Research',
  portfolio: 'Your Portfolio',
  status: 'System Status',
}

export function AppHeader({
  active,
  locations,
}: {
  active: View
  locations: Partial<Record<View, string>>
}) {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <a
          href={locations.briefing || '/?view=briefing'}
          data-section="briefing"
          className="wordmark"
          aria-label="FINN home"
        >
          finn<span>.</span>
        </a>
        <Navigation active={active} placement="desktop" locations={locations} />
        <ThemeSelector />
      </div>
    </header>
  )
}

export function PageHeading({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="page-heading">
      <h1>{title}</h1>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function AppFooter({ children }: { children?: ReactNode }) {
  return (
    <footer className="app-footer">
      {children}
      <a href="/?view=status">System status</a>
    </footer>
  )
}
