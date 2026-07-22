# Project instructions

## Purpose

This repository contains Elia's static AI product portfolio and an auxiliary local Figma/FigJam plugin.

## Run

- No install or build step is required.
- From the repository root, run `python -m http.server 8000` and open `http://localhost:8000/`.

## Stack

- Standalone HTML, CSS, and browser JavaScript
- Local JPG, PNG, and MP4 assets
- Figma plugin files in `vibma-plugin/`

## Structure and conventions

- Keep page-specific CSS and JavaScript within the existing standalone HTML files unless a deliberate shared-asset refactor is requested.
- Preserve the film-inspired visual language and bilingual Chinese/English copy.
- Use relative paths for repository-owned pages and media.
- Do not duplicate or recompress large media without an explicit request.
- Treat both Douban snapshots as atomic deployable units: commit `movies.json` with `covers/`, and `books.json` with `book-covers/`; keep `assets/douban-placeholder.svg` available to both.
- Keep `assets/thoughts-data.js` limited to `text`, `date`, `category`, and optional `featured`; do not reintroduce per-card scene labels.
- Keep the enlarged Thought polaroid, scrolling behavior, background lock, and metadata layout synchronized between `index.html` and `thoughts.html`.
- Treat `.cursor/mcp.json` as local integration configuration; never add credentials to it.
- Preserve unrelated working-tree changes and inspect `git diff` before editing.

## Current state and next step

- The site has no automated test suite or deployment configuration in this repository.
- The About reading and cinema archives fetch local JSON, so test through HTTP rather than `file://`.
- Refresh movies with `python scripts/sync_douban_movies.py --expected-total 211` and books with `python scripts/sync_douban_books.py --expected-total 23`, then verify each JSON count and every referenced cover.
- Verify changed pages through a local static server at desktop and mobile widths; test the Figma plugin separately in Figma Desktop when it changes.
