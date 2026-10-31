import { useSyncExternalStore } from 'react'

type ThemePreference = 'light' | 'dark' | 'system'

declare global {
  interface Window {
    finnTheme: {
      getPreference: () => ThemePreference
      setPreference: (preference: ThemePreference) => void
    }
  }
}

const subscribe = (notify: () => void) => {
  window.addEventListener('finn-theme-change', notify)
  return () => window.removeEventListener('finn-theme-change', notify)
}
const snapshot = () => window.finnTheme.getPreference()

export default function ThemeSelector() {
  const preference = useSyncExternalStore(subscribe, snapshot)
  return (
    <label className="theme-picker" title={`Colour theme: ${preference}`}>
      <span className="sr-only">Colour theme</span>
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        aria-hidden="true"
      >
        {preference === 'dark' ? (
          <path d="M20 14a8.5 8.5 0 0 1-10-10A8.5 8.5 0 1 0 20 14Z" />
        ) : preference === 'light' ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" />
          </>
        ) : (
          <>
            <rect x="3" y="4" width="18" height="13" rx="2" />
            <path d="M8 21h8m-4-4v4" />
          </>
        )}
      </svg>
      <select
        value={preference}
        onChange={(event) => window.finnTheme.setPreference(event.target.value as ThemePreference)}
      >
        <option value="light">Light</option>
        <option value="dark">Dark</option>
        <option value="system">System</option>
      </select>
      <svg
        className="theme-chevron"
        width="8"
        height="8"
        viewBox="0 0 12 12"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        aria-hidden="true"
      >
        <path d="m2 4 4 4 4-4" />
      </svg>
    </label>
  )
}
