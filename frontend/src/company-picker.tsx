import { useEffect, useId, useMemo, useRef, useState } from 'react'
import {
  createCompanySearch,
  loadCompanyDirectory,
  type Directory,
  type DirectoryCompany,
} from './company-search'

export default function CompanyPicker({
  symbol,
  watchlist,
  disabled,
  onSelect,
  onEditing,
}: {
  symbol: string
  watchlist: DirectoryCompany[]
  disabled: boolean
  onSelect: (symbol: string) => void
  onEditing: (editing: boolean) => void
}) {
  const [directory, setDirectory] = useState<Directory | null>(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(-1)
  const [hint, setHint] = useState('')
  const [allWatchlist, setAllWatchlist] = useState(false)
  const [recent, setRecent] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('finn-recent-companies') || '[]')
        .filter((value: unknown) => typeof value === 'string')
        .slice(0, 4)
    } catch {
      return []
    }
  })
  const input = useRef<HTMLInputElement>(null)
  const change = useRef<HTMLButtonElement>(null)
  const listId = useId()
  const load = () => {
    setError('')
    void loadCompanyDirectory()
      .then(setDirectory)
      .catch(() =>
        setError(
          'Company search is temporarily unavailable. You can still choose from your watchlist.',
        ),
      )
  }
  useEffect(load, [])
  useEffect(() => {
    if (active >= 0)
      document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: 'nearest' })
  }, [active, listId])
  const companies = directory?.companies || watchlist
  const search = useMemo(() => createCompanySearch(companies), [companies])
  const matches = search(query)
  const selected =
    watchlist.find((company) => company.symbol === symbol) ||
    companies.find((company) => company.symbol === symbol)
  function edit(value: boolean) {
    setEditing(value)
    onEditing(value)
    setActive(-1)
    setHint('')
    if (value) {
      setQuery('')
      requestAnimationFrame(() => input.current?.focus())
    } else requestAnimationFrame(() => change.current?.focus())
  }
  function choose(value: string) {
    onSelect(value)
    setEditing(false)
    onEditing(false)
    setQuery('')
    setActive(-1)
    setAllWatchlist(false)
    const next = [value, ...recent.filter((item) => item !== value)].slice(0, 4)
    setRecent(next)
    try {
      localStorage.setItem('finn-recent-companies', JSON.stringify(next))
    } catch {
      /* Session only. */
    }
    requestAnimationFrame(() => change.current?.focus())
  }
  return (
    <div className="company-picker">
      <div className="selected-company" aria-label="Selected company">
        <div>
          <span className="field-label">Company</span>
          <strong>{selected?.name || symbol}</strong>
          <span className="selected-symbol">
            {symbol} <small>NSE</small>
          </span>
        </div>
        <button
          type="button"
          className="text-button"
          disabled={disabled}
          ref={change}
          onClick={() => edit(!editing)}
          aria-expanded={editing}
        >
          {editing ? 'Cancel change' : 'Change company'}
        </button>
      </div>
      {editing && (
        <div className="company-discovery">
          <label htmlFor={listId + '-input'}>Find a company</label>
          <input
            id={listId + '-input'}
            ref={input}
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={!!query}
            aria-controls={listId}
            aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
            value={query}
            autoComplete="off"
            spellCheck={false}
            placeholder="Company name, symbol or abbreviation"
            disabled={disabled}
            onChange={(event) => {
              setQuery(event.target.value)
              setActive(-1)
              setHint('')
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                event.preventDefault()
                edit(false)
              } else if (event.key === 'ArrowDown') {
                event.preventDefault()
                setActive((index) => Math.min(matches.length - 1, index + 1))
              } else if (event.key === 'ArrowUp') {
                event.preventDefault()
                setActive((index) => Math.max(0, index - 1))
              } else if (event.key === 'Enter') {
                event.preventDefault()
                if (active >= 0 && matches[active]) choose(matches[active].symbol)
                else if (matches.length === 1) choose(matches[0].symbol)
                else setHint('Select the intended company from the suggestions.')
              }
            }}
          />
          {query && (
            <ul
              className="company-suggestions"
              role="listbox"
              id={listId}
              aria-label="Company suggestions"
            >
              {matches.map((company, index) => (
                <li
                  key={company.symbol}
                  role="option"
                  id={`${listId}-${index}`}
                  aria-selected={index === active}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(company.symbol)}
                  onMouseMove={() => setActive(index)}
                >
                  <span>{company.name}</span>
                  <small>{company.symbol}</small>
                </li>
              ))}
            </ul>
          )}
          {query && !matches.length && (
            <p className="company-search-note" role="status">
              No matching listing found. Try a shorter name or check the spelling.
            </p>
          )}
          {hint && (
            <p className="company-search-note" role="status">
              {hint}
            </p>
          )}
          {error && (
            <p className="company-search-note" role="status">
              {error}{' '}
              <button type="button" className="text-button" onClick={load}>
                Retry directory
              </button>
            </p>
          )}
          {directory && (
            <small className="directory-date">
              NSE directory ·{' '}
              {new Date(directory.checked_at).toLocaleDateString('en-IN', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })}
            </small>
          )}
        </div>
      )}
      <div className="watchlist-access">
        <button
          type="button"
          className="text-button"
          aria-expanded={allWatchlist}
          disabled={disabled || !watchlist.length}
          onClick={() => setAllWatchlist(!allWatchlist)}
        >
          Watchlist · {allWatchlist ? 'Hide companies' : `View all ${watchlist.length || 15}`}
        </button>
        {editing &&
          !query &&
          !allWatchlist &&
          recent.filter((value) => value !== symbol).length > 0 && (
            <div className="recent-companies" aria-label="Recent companies">
              <span>Recent</span>
              {recent
                .filter((value) => value !== symbol)
                .slice(0, 2)
                .map((value) => {
                  const company =
                    watchlist.find((company) => company.symbol === value) ||
                    companies.find((company) => company.symbol === value)
                  return company ? (
                    <button
                      type="button"
                      key={value}
                      disabled={disabled}
                      onClick={() => choose(value)}
                    >
                      {company.name} <small>{value}</small>
                    </button>
                  ) : null
                })}
            </div>
          )}
      </div>
      {allWatchlist && (
        <div className="watchlist-picker" aria-label="Watchlist companies">
          {watchlist.map((company) => (
            <button
              type="button"
              key={company.symbol}
              disabled={disabled}
              aria-pressed={symbol === company.symbol}
              onClick={() => choose(company.symbol)}
            >
              <span>{company.name}</span>
              <small>{company.symbol}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
