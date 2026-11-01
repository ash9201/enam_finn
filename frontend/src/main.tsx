import React, { useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import ResearchApp from './research'
import './research.css'
import BriefingApp from './briefing'
import './briefing.css'
import { RecordedDataNotice } from './data'
import Navigation, { type View } from './navigation'
import { AppHeader, PAGE_TITLES } from './layout'
import SystemStatus from './system-status'
import './layout.css'

function viewOf(url: string): View {
  const view = new URL(url, window.location.origin).searchParams.get('view')
  if (view === 'research' || view === 'portfolio' || view === 'status') return view
  return view === 'foundation' ? 'status' : 'briefing'
}

function Application() {
  const [url, setUrl] = useState(window.location.pathname + window.location.search)
  const view = viewOf(url)
  const [visited, setVisited] = useState<View[]>([view])
  const [researchEntry, setResearchEntry] = useState(0)
  const [briefingEntry, setBriefingEntry] = useState(0)
  const locations = useRef<Partial<Record<View, string>>>({ [view]: url })
  const lastSection = useRef<View>(view === 'status' ? 'briefing' : view)
  const scrollPositions = useRef<Partial<Record<View, number>>>({})
  const pages = useRef<Partial<Record<View, HTMLDivElement | null>>>({})
  const shouldFocus = useRef(false)

  function navigate(
    nextUrl: string,
    push = true,
    explicitResearch = false,
    explicitBriefing = false,
  ) {
    const next = viewOf(nextUrl)
    if (explicitBriefing) {
      setBriefingEntry((value) => value + 1)
      scrollPositions.current.briefing = 0
    }
    if (
      next === 'research' &&
      locations.current.research &&
      (explicitResearch || locations.current.research !== nextUrl)
    ) {
      setResearchEntry((value) => value + 1)
      scrollPositions.current.research = 0
    }
    if (push && nextUrl !== window.location.pathname + window.location.search)
      window.history.pushState(null, '', nextUrl)
    locations.current[next] = nextUrl
    if (next !== 'status') lastSection.current = next
    setVisited((previous) => (previous.includes(next) ? previous : [...previous, next]))
    shouldFocus.current = true
    setUrl(nextUrl)
  }

  useEffect(() => {
    const onPop = () => navigate(window.location.pathname + window.location.search, false)
    window.addEventListener('popstate', onPop)
    const onResearchLocation = (event: Event) => {
      const location = (event as CustomEvent<string>).detail
      if (viewOf(location) !== 'research') return
      locations.current.research = location
      setUrl(location)
    }
    window.addEventListener('finn:research-location', onResearchLocation)
    return () => {
      window.removeEventListener('popstate', onPop)
      window.removeEventListener('finn:research-location', onResearchLocation)
    }
  }, [])

  useLayoutEffect(() => {
    document.title = `${PAGE_TITLES[view]} | FINN`
    const page = pages.current[view]
    if (page) page.scrollTop = scrollPositions.current[view] || 0
    if (shouldFocus.current) {
      page?.querySelector<HTMLElement>('main')?.focus({ preventScroll: true })
      shouldFocus.current = false
    }
  }, [url, view])

  function onLink(event: MouseEvent<HTMLDivElement>) {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    )
      return
    const anchor = (event.target as Element).closest<HTMLAnchorElement>('a[href]')
    if (!anchor || anchor.hasAttribute('download') || (anchor.target && anchor.target !== '_self'))
      return
    const target = new URL(anchor.href)
    if (target.origin !== window.location.origin || target.pathname !== '/' || target.hash) return
    event.preventDefault()
    const explicitResearch =
      !anchor.dataset.section &&
      !anchor.hasAttribute('data-return-to-finn') &&
      viewOf(target.href) === 'research' &&
      ['symbol', 'analysis', 'question', 'refresh'].some((key) => target.searchParams.has(key))
    const explicitBriefing =
      !anchor.dataset.section &&
      viewOf(target.href) === 'briefing' &&
      target.searchParams.has('company')
    navigate(target.pathname + target.search, true, explicitResearch, explicitBriefing)
  }

  return (
    <div className="app-shell" onClick={onLink}>
      <a className="skip-link" href={`#${view}-content`}>
        Skip to content
      </a>
      <RecordedDataNotice />
      <AppHeader active={view} locations={locations.current} />
      <div className="app-views">
        {visited.map((section) => (
          <div
            key={section}
            className="app-view"
            data-view={section}
            hidden={section !== view}
            inert={section !== view}
            ref={(element) => {
              pages.current[section] = element
            }}
            onScroll={(event) => {
              if (section === view) scrollPositions.current[section] = event.currentTarget.scrollTop
            }}
          >
            {section === 'research' ? (
              <ResearchApp key={researchEntry} active={view === section} />
            ) : section === 'status' ? (
              <SystemStatus
                returnHref={locations.current[lastSection.current] || '/?view=briefing'}
                active={view === section}
              />
            ) : (
              <BriefingApp
                portfolio={section === 'portfolio'}
                active={view === section}
                entryUrl={locations.current[section]}
                entryKey={briefingEntry}
              />
            )}
          </div>
        ))}
      </div>
      <Navigation active={view} placement="mobile" locations={locations.current} />
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Application />
  </React.StrictMode>,
)
