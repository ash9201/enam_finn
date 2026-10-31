// Runs synchronously before the application/styles paint. Never depends on React.
;(() => {
  const key = 'finn-theme'
  const normalise = (value) => (['light', 'dark', 'system'].includes(value) ? value : 'system')
  const read = () => {
    try {
      return normalise(localStorage.getItem(key))
    } catch {
      return 'system'
    }
  }
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  let preference = read()
  function apply() {
    document.documentElement.dataset.theme =
      preference === 'system' ? (media.matches ? 'dark' : 'light') : preference
    document.documentElement.dataset.themePreference = preference
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta)
      meta.content = getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim()
    window.dispatchEvent(new Event('finn-theme-change'))
  }
  window.finnTheme = {
    getPreference: () => preference,
    setPreference(value) {
      preference = normalise(value)
      try {
        localStorage.setItem(key, preference)
      } catch {
        /* The session still works when storage is blocked. */
      }
      apply()
    },
  }
  media.addEventListener('change', () => {
    if (preference === 'system') apply()
  })
  window.addEventListener('storage', (event) => {
    if (event.key === key || event.key === null) {
      preference = event.key === null ? read() : normalise(event.newValue)
      apply()
    }
  })
  apply()
})()
