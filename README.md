# SPIE AS26 Schedule Viewer

## [→ spie2026.netlify.app](https://spie2026.netlify.app/)

An unofficial schedule viewer for [SPIE Astronomical Telescopes + Instrumentation 2026](https://spie.org/conferences-and-exhibitions/astronomical-telescopes-and-instrumentation) (Copenhagen, Sun 5 – Fri 10 July 2026), covering 3191 talks and 2140 posters across 13 conferences.

- Sun 5 Jul: 160 talks across 9 rooms
- Mon 6 Jul: 181 talks across 13 rooms
- Tue 7 Jul: 214 talks across 14 rooms
- Wed 8 Jul: 187 talks across 14 rooms
- Thu 9 Jul: 152 talks across 12 rooms
- Fri 10 Jul: 157 talks across 9 rooms
- 2140 poster entries across 5 days

## Features

- **Views** — Schedule grid, Talk List, Talk Swipe, Poster List, and Poster Swipe
- **Day tabs** — switch between Sun 5 Jul through Fri 10 Jul
- **Live search** — search bar adapts to the active view; `Escape` clears
- **Track filter** — click any conference in the legend to filter; multi-select supported
- **Talk detail modal** — click any title for the full abstract and a link to the SPIE page
- **Bookmarks** — click ☆ on any talk or poster; persists across sessions
- **Skip** — mark talks/posters as not interested; hidden in My Schedule mode
- **My Schedule** — toggle in the topbar to show only bookmarked items across all views
- **Swipe mode** — Tinder-style triage for both talks and posters (bookmark or skip with a swipe)
- **Cross-device sync** — optional anonymous sync via a personal code; no account required (see below)
- **Manual backup** — export/import bookmarks as plain text

## Cross-device sync

Bookmarks and skipped items are saved in your browser's `localStorage`. To sync across devices:

1. Open **Sync & Backup** (the ⇕ icon in the top bar)
2. Click **Copy Link** and open it on your other device — it will sync automatically
3. Changes propagate within ~30 seconds, or instantly when you switch back to the tab

Sync is anonymous: a random 12-character code is generated per browser and stored locally. No account, no email, no personal data is ever sent. Data is stored on Cloudflare KV and expires after 90 days of inactivity.

## Files

| File | Purpose |
|---|---|
| `spie_query.py` | Fetches presentation data from the SPIE API and saves JSON to `spie_query_results/` |
| `build_html.py` | Reads the JSON and generates `output/index.html` |
| `spie_query_results/` | Raw JSON from the SPIE API |
| `output/index.html` | The generated schedule viewer |
| `worker/` | Cloudflare Worker that handles cross-device sync |

## Usage

Requires [uv](https://docs.astral.sh/uv/).

### 1. Fetch data

```bash
uv run spie_query.py
```

Paginates through the SPIE search API and saves results to `spie_query_results/`. If the API requires authentication, paste your browser session cookies into the `COOKIES` dict at the top of the file.

Plenary sessions are not in the standard pagination — fetch them separately and save as `spie_query_results/plenary.json` (using `TypeSecondary=Plenary_Event` in the query).

### 2. Build

```bash
uv run build_html.py
open output/index.html
```

### 3. Deploy the sync worker (optional)

```bash
cd worker
wrangler deploy
```

Then set `SYNC_API_URL` in `build_html.py` to your worker's URL and rebuild.

## Conferences included

| Code | Title |
|---|---|
| 14145 | Space Telescopes and Instrumentation: Optical, Infrared, and Millimeter Wave |
| 14146 | Space Telescopes and Instrumentation: Ultraviolet to Gamma Ray |
| 14147 | Ground-based and Airborne Telescopes XI |
| 14148 | Optical and Infrared Interferometry and Imaging X |
| 14149 | Ground-based and Airborne Instrumentation for Astronomy XI |
| 14150 | Adaptive Optics Systems X |
| 14151 | Observatory Operations |
| 14152 | Modeling, Systems Engineering, and Project Management for Astronomy XII |
| 14153 | Radio Telescopes, Technologies, and Methods |
| 14154 | Advances in Optical and Mechanical Technologies for Telescopes and Instrumentation VII |
| 14155 | Software and Cyberinfrastructure for Astronomy IX |
| 14156 | Millimeter, Submillimeter, and Far-Infrared Detectors and Instrumentation for Astronomy XIII |
| 14157 | X-Ray, Optical, and Infrared Detectors for Astronomy XII |

To add or remove conferences, edit `CONFERENCES_OF_INTEREST`, `CONF_SHORT`, and `CONF_COLOR` in `build_html.py`, then rebuild.

## Notes

- Conference 14149 had no room assignments in the SPIE data at time of scraping; its talks appear under a **Room TBC** column. Re-run `spie_query.py` and `build_html.py` once SPIE publishes room assignments.
- The HTML file is fully self-contained (no external dependencies) and can be opened from any local path or shared folder without a server.
