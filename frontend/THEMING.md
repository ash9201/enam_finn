# FINN themes

Light, Dark and System are available from the header on every view. The preference
is saved under `finn-theme` in localStorage. Missing or invalid values use System;
system changes apply immediately in that mode. Other tabs stay in sync. If storage
is blocked, selection still works for the current page session.

- `public/theme.css` owns the shared semantic palette, including surfaces, text,
  controls, warnings, success and financial positive/negative indicators.
- `public/theme-init.js` runs synchronously in the head before the app bundle. It
  sets the resolved root theme and browser chrome colour before React renders.
- `src/theme.tsx` subscribes to that controller and renders an accessible native
  selector. Mobile keeps a 44px target with an appearance icon; desktop shows the
  selected label. Native form controls follow the resolved `color-scheme`.
- Component styles use tokens, with no separate hardcoded dark overrides. New
  components should follow the same pattern. The existing geometry/type remains.

From the workspace root, with the portable Node toolchain already configured:

```powershell
python scripts/npm.py run build
python scripts/npm.py run preview -- --port 4173
```

In a second terminal:

```powershell
python scripts/npm.py run test:theme
```

The browser suite covers light/dark at 390px and 1440px, a 320px layout check,
saved/default/system behaviour, cross-tab changes, blocked storage, startup before
React, visible text contrast, evidence dialogs, forms, loading and error states.
It uses the explicitly dated public snapshot and simulated transport responses;
it makes no source/model writes. Screenshots and results stay in ignored
`artifacts/theme-browser/`. Set `FINN_BROWSER_URL` to check the deployed frontend.
