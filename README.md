# Elia's Film Roll

A static, daylight film-editorial portfolio for AI product work. The site uses standalone HTML pages, shared vanilla JavaScript modules, and local image/video assets; it has no package manager or build step.

## Pages

- `index.html` — Opening, horizontal project film strip, featured Thoughts, and project detail overlays
- `about.html` — tabbed personal profile, off-camera interests, and contact links
- `thoughts.html` — filterable archive of all Thoughts
- `assets/theme.js` — persistent day/darkroom theme controller
- `assets/thoughts-data.js` — shared Thoughts data used by both content pages
- `vibma-plugin/` — a separate local Figma/FigJam plugin used through a Vibma WebSocket relay

## Run locally

From the repository root, start any static file server. For example:

```powershell
python -m http.server 8000
```

Then open `http://localhost:8000/`. Serving the files is preferred to opening them directly so navigation and media use normal browser URL behavior.

## Verification

There is no automated test suite. Before handing off a change:

1. Check `index.html`, `about.html`, and `thoughts.html` at 1440px, 1024px, and 390px widths.
2. Exercise the project film strip with drag, wheel, touch, and keyboard input.
3. Follow all local navigation links and verify modal/overlay close and focus-restoration behavior.
4. Confirm the day/darkroom choice persists across all three pages.
5. Confirm local videos use metadata preload and local images load without console errors.
6. If editing `vibma-plugin/`, import its `manifest.json` in Figma Desktop and test the local relay connection separately.

External fonts and the MoodMix link require network access. Large media files are committed to the repository, so avoid creating duplicate exports in the project root.
