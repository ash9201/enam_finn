export type DirectoryCompany = { symbol: string; name: string; aliases?: string[]; isin?: string }
export type Directory = { checked_at: string; sources: string[]; companies: DirectoryCompany[] }
export const normalizeCompany = (value: string) =>
  value
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]/g, '')
const shortName = (name: string) => name.replace(/\b(?:limited|ltd|private|pvt)\b\.?/gi, '').trim()
const words = (name: string) =>
  shortName(name)
    .toLowerCase()
    .replace(/&/g, ' ')
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
function distance(a: string, b: string, limit: number) {
  if (Math.abs(a.length - b.length) > limit) return limit + 1
  const rows = Array.from({ length: a.length + 1 }, (_, i) =>
    Array.from({ length: b.length + 1 }, (_, j) => (i ? (j ? 0 : i) : j)),
  )
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++) {
      rows[i][j] = Math.min(
        rows[i - 1][j] + 1,
        rows[i][j - 1] + 1,
        rows[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      )
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1])
        rows[i][j] = Math.min(rows[i][j], rows[i - 2][j - 2] + 1)
    }
  return rows[a.length][b.length]
}
export function createCompanySearch(companies: DirectoryCompany[]) {
  const indexed = companies.map((company) => ({
    company,
    symbol: normalizeCompany(company.symbol),
    bareSymbol: company.symbol.toLowerCase().replace(/[^a-z0-9]/g, ''),
    name: normalizeCompany(shortName(company.name)),
    words: words(company.name),
    aliases: (company.aliases || []).flatMap((alias) => [
      normalizeCompany(alias),
      normalizeCompany(shortName(alias)),
    ]),
    initials: [company.name, ...(company.aliases || [])].flatMap((name) => [
      words(name)
        .map((word) => word[0])
        .join(''),
      name
        .toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter(Boolean)
        .map((word) => word[0])
        .join(''),
    ]),
  }))
  return (query: string, limit = 8): DirectoryCompany[] => {
    query = query.replace(/\.NS$/i, '')
    const q = normalizeCompany(query),
      short = normalizeCompany(shortName(query)),
      bare = query
        .toLowerCase()
        .replace(/\band\b/g, '')
        .replace(/[^a-z0-9]/g, ''),
      terms = words(query).filter((word) => word.length >= 2)
    if (!q) return []
    const ranked = indexed.map((entry) => {
      let score = Infinity
      if (entry.symbol === q || entry.bareSymbol === bare) score = 0
      else if (entry.name === q || (short && entry.name === short)) score = 1
      else if (entry.symbol.startsWith(q) || entry.name.startsWith(q)) score = 2
      else if (entry.aliases.includes(q) || entry.initials.includes(q)) score = 3
      else if (
        terms.length &&
        terms.every((term) => entry.words.some((word) => word.startsWith(term)))
      )
        score = 4
      else if (
        (!query.includes('&') && entry.name.includes(q)) ||
        entry.aliases.some((alias) => alias.startsWith(q))
      )
        score = 5
      return { ...entry, score }
    })
    if (!ranked.some((entry) => entry.score < Infinity) && q.length >= 4) {
      const tolerance = q.length >= 7 ? 2 : 1
      for (const entry of ranked) {
        if (entry.score < Infinity) continue
        const candidates = [entry.symbol, entry.name, ...entry.aliases]
        const error = Math.min(
          ...candidates.map((value) =>
            distance(q, value.slice(0, q.length + tolerance), tolerance),
          ),
        )
        const wordError = Math.min(
          ...entry.words.map((value) =>
            distance(q, value.slice(0, q.length + tolerance), tolerance),
          ),
        )
        if (error <= tolerance) entry.score = 10 + error * 3
        else if (wordError <= tolerance) entry.score = 12 + wordError * 3
      }
    }
    return ranked
      .filter((entry) => entry.score < Infinity)
      .sort(
        (a, b) =>
          a.score - b.score ||
          (a.score === 2 ? a.name.length - b.name.length : 0) ||
          a.company.name.localeCompare(b.company.name),
      )
      .slice(0, limit)
      .map((entry) => entry.company)
  }
}
let directoryRequest: Promise<Directory> | null = null
export function loadCompanyDirectory() {
  if (!directoryRequest)
    directoryRequest = fetch('/company-directory.json')
      .then(async (response) => {
        if (!response.ok) throw new Error('The company directory could not be loaded.')
        const directory = (await response.json()) as Directory
        if (!directory.companies?.length) throw new Error('The company directory is empty.')
        return directory
      })
      .catch((error) => {
        directoryRequest = null
        throw error
      })
  return directoryRequest
}
