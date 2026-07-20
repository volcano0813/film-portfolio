# Elia's Film Roll

A static, film-inspired portfolio for AI product work. The site is written as standalone HTML pages with local image and video assets; it has no package manager or build step.

## Pages

- `index.html` — portfolio landing page and project details
- `about.html` — personal profile and contact links
- `thoughts.html` — notes on AI product work
- `vibma-plugin/` — a separate local Figma/FigJam plugin used through a Vibma WebSocket relay

## Run locally

From the repository root, start any static file server. For example:

```powershell
python -m http.server 8000
```

Then open `http://localhost:8000/`. Serving the files is preferred to opening them directly so navigation and media use normal browser URL behavior.

## Verification

There is no automated test suite. Before handing off a change:

1. Check `index.html`, `about.html`, and `thoughts.html` at desktop and mobile widths.
2. Follow all local navigation links and verify modal/overlay close behavior.
3. Confirm the three local videos and local images load.
4. If editing `vibma-plugin/`, import its `manifest.json` in Figma Desktop and test the local relay connection separately.

External fonts and the MoodMix link require network access. Large media files are committed to the repository, so avoid creating duplicate exports in the project root.
