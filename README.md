# SPIE AS26 Schedule Viewer

A self-contained HTML schedule for [SPIE Astronomical Telescopes + Instrumentation 2026](https://spie.org/conferences-and-exhibitions/astronomical-telescopes-and-instrumentation) (Copenhagen, Sun 5 to Fri 10 July 2026).

## Files

| File | Purpose |
|---|---|
| `spie_query.py` | Fetches paginated presentation data from the SPIE search API and saves each page as JSON to `spie_query_results/` |
| `build_html.py` | Reads the JSON pages and generates `output/index.html` |
| `spie_query_results/` | Raw JSON from the SPIE API (one file per page of 50 results, plus `plenary.json`) |
| `output/index.html` | The generated schedule viewer |

## Usage

Requires [uv](https://docs.astral.sh/uv/).

### 1. Fetch data

```bash
python spie_query.py
```

This paginates through the SPIE search API and saves results to `spie_query_results/`. If the API requires authentication, paste your browser session cookies into the `COOKIES` dict at the top of the file.

Plenary sessions are not included in the standard pagination — fetch them separately and save as `spie_query_results/plenary.json` (using `TypeSecondary=Plenary_Event` in the query).

### 2. Build the HTML schedule

```bash
uv run build_html.py
open output/index.html
```

## HTML schedule features

- **Day tabs** — switch between Sun 5 Jul through Fri 10 Jul
- **Live search** — type in the topbar to filter by title, author, paper number, or keyword; `Escape` clears
- **Colour-coded conferences** — each of the 13 included conferences has a distinct colour; legend shown above the grid
- **Poster sessions** — rows for 17:30–19:00 are highlighted amber
- **Talk links** — titles link directly to the SPIE abstract page
- **Bookmarks** — click the ☆ on any card to save a talk; bookmarks persist in `localStorage`
- **My Schedule** — toggle in the topbar to show only bookmarked talks
- **Export / Import** — copies bookmarks as a plain JSON array of paper IDs, for transferring between devices

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

To add or remove conferences, edit `CONFERENCES_OF_INTEREST`, `CONF_SHORT`, and `CONF_COLOR` in `build_html.py`, then re-run step 2.

## Notes

- Conference 14149 had no room assignments in the SPIE data at time of scraping; its talks appear under a **Room TBC** column. Re-run `spie_query.py` and `build_html.py` once SPIE publishes room assignments.
- The HTML file is fully self-contained (no external dependencies) and can be opened from any local file path or shared folder.
