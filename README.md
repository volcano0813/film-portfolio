# Elia's Film Roll

A static, daylight film-editorial portfolio for AI product work. The site uses standalone HTML pages, shared vanilla JavaScript modules, and local image/video assets; it has no package manager or build step.

## Pages

- `index.html` — Opening, horizontal project film strip, featured Thoughts, and project detail overlays
- `about.html` — pannable life contact sheet, off-camera interests, contact links, and a searchable cinema archive
- `thoughts.html` — filterable archive of all Thoughts
- `assets/theme.js` — persistent day/darkroom theme controller
- `assets/thoughts-data.js` — shared Thoughts data used by both content pages
- `vibma-plugin/` — a separate local Figma/FigJam plugin used through a Vibma WebSocket relay

## Run locally

From the repository root, start any static file server. For example:

```powershell
python -m http.server 8000
```

Then open `http://localhost:8000/`. Always serve the files over HTTP: opening `about.html` through `file://` prevents the cinema archive from fetching its local JSON snapshot.

## Verification

There is no automated test suite. Before handing off a change:

1. Check `index.html`, `about.html`, and `thoughts.html` at 1440px, 1024px, and 390px widths.
2. Exercise the project film strip with drag, wheel, touch, and keyboard input.
3. Follow all local navigation links and verify modal/overlay close and focus-restoration behavior.
4. Confirm the day/darkroom choice persists across all three pages.
5. Confirm local videos use metadata preload and local images load without console errors.
6. Open `about.html#cinema`; verify all 211 entries load, then exercise search, five-star filtering, sorting, progressive loading, movie details, Escape/Tab behavior, and a missing-poster fallback.
7. If editing `vibma-plugin/`, import its `manifest.json` in Figma Desktop and test the local relay connection separately.

External fonts and the MoodMix link require network access. Large media files are committed to the repository, so avoid creating duplicate exports in the project root.

## Refresh the Douban movie archive

The About page uses a committed, local snapshot of Elia's public "watched" movie list. It never requests Douban at runtime and the snapshot contains no account cookies or outbound movie links.

From the repository root, run:

```powershell
python scripts/sync_douban_movies.py --expected-total 211
```

The script uses only Python's standard library. It waits one second between collection pages, reuses valid existing posters, downloads new posters as WebP, and replaces `assets/douban/movies.json` only after the entire collection has been parsed and validated. If the collection grows, update or omit `--expected-total` after confirming the new total.

Commit `assets/douban/movies.json`, every referenced file under `assets/douban/covers/`, and `assets/douban-placeholder.svg` together. The deployed page and snapshot are same-origin static assets; no Douban request is made in a visitor's browser.
