import { useEffect, useState } from 'react'

const url = (import.meta.env.VITE_SUPABASE_URL || '').replace(/\/$/, '')
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || ''
type Snapshot = {
  mode: string
  exported_at: string
  tables: Record<string, Record<string, unknown>[]>
}
let snapshot: Promise<Snapshot> | undefined
let recordedAt: string | null = null

async function recordedRead(table: string, query: Record<string, string>) {
  snapshot ??= fetch('/recorded-snapshot.json').then((response) => {
    if (!response.ok) throw new Error('No recorded snapshot is available.')
    return response.json()
  })
  const data = await snapshot
  if (data.mode !== 'recorded_demo_snapshot' || !data.exported_at)
    throw new Error('Invalid recorded snapshot.')
  let rows = [...(data.tables[table] || [])]
  for (const [field, value] of Object.entries(query)) {
    if (value.startsWith('eq.')) rows = rows.filter((row) => String(row[field]) === value.slice(3))
  }
  if (query.order) {
    const [field, direction] = query.order.split('.')
    rows.sort(
      (a, b) => String(a[field]).localeCompare(String(b[field])) * (direction === 'desc' ? -1 : 1),
    )
  }
  if (query.limit) rows = rows.slice(0, Number(query.limit))
  recordedAt = data.exported_at
  window.dispatchEvent(new Event('finn-recorded-data'))
  return rows
}

export async function publicRead(table: string, query: Record<string, string>) {
  try {
    if (!url || !key) throw new Error('Public cache is not configured.')
    const response = await fetch(`${url}/rest/v1/${table}?${new URLSearchParams(query)}`, {
      headers: { apikey: key },
      signal: AbortSignal.timeout(12000),
    })
    if (!response.ok) throw new Error('Live saved updates are unavailable.')
    return await response.json()
  } catch (error) {
    try {
      return await recordedRead(table, query)
    } catch {
      throw error
    }
  }
}

export function RecordedDataNotice() {
  const [date, setDate] = useState(recordedAt)
  useEffect(() => {
    const update = () => setDate(recordedAt)
    window.addEventListener('finn-recorded-data', update)
    update()
    return () => window.removeEventListener('finn-recorded-data', update)
  }, [])
  if (!date) return null
  const label = new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'Asia/Kolkata',
  }).format(new Date(date))
  return (
    <div className="recorded-notice" role="status">
      <strong>Recorded demo snapshot · {label} IST.</strong> Live saved updates could not be read.
      Some information below is historical; original source dates are shown.
    </div>
  )
}
