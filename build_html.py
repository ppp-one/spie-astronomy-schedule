#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate a self-contained HTML schedule for selected SPIE AS26 conferences."""

import html as _html
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "spie_query_results"
OUTPUT_DIR = Path(__file__).parent / "output"

CONFERENCES_OF_INTEREST = {
    "14145",
    "14146",
    "14147",
    "14148",
    "14149",
    "14150",
    "14151",
    "14152",
    "14153",
    "14154",
    "14155",
    "14156",
    "14157",
}

CONF_SHORT = {
    "14145": "Space Tel: Opt/IR/mm",
    "14146": "Space Tel: UV–γ",
    "14147": "Ground/Airborne Tel",
    "14148": "Interferometry",
    "14149": "Ground/Airborne Instr",
    "14150": "Adaptive Optics",
    "14151": "Observatory Ops",
    "14152": "Sys Eng & PM",
    "14153": "Radio Telescopes",
    "14154": "Opt/Mech Tech",
    "14155": "Software & Cyber",
    "14156": "mm/Submm/FIR Det",
    "14157": "Detectors (X/Opt/IR)",
    "PLENARY": "Plenary",
}

CONF_COLOR = {
    "14145": "#b07aa1",
    "14146": "#c9a800",
    "14147": "#d4606a",
    "14148": "#7fb3d3",
    "14149": "#f28e2b",
    "14150": "#17becf",
    "14151": "#9c755f",
    "14152": "#e15759",
    "14153": "#aec7e8",
    "14154": "#4e79a7",
    "14155": "#3aaa8c",
    "14156": "#6b9e78",
    "14157": "#59a14f",
    "PLENARY": "#ffffff",
}

MONTH_MAP = {
    m: i
    for i, m in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        1,
    )
}

DTL_RE = re.compile(
    r"^(?P<date>.+?)\s+•\s+(?P<time_slot>.+?)(?:\s+\|\s+(?P<room>.+))?$"
)


def e(s: str) -> str:
    return _html.escape(str(s), quote=True)


def parse_dtl(s: str):
    m = DTL_RE.match(s.strip())
    if not m:
        return None
    room = (m.group("room") or "").strip() or "Room TBC"
    return (m.group("date"), m.group("time_slot"), room)


def date_to_iso(date_str: str) -> str:
    parts = date_str.strip().split()
    return f"{parts[2]}-{MONTH_MAP[parts[1]]:02d}-{int(parts[0]):02d}"


def slot_sort_key(ts: str) -> datetime:
    return datetime.strptime(ts.split("-")[0].strip().split()[0], "%H:%M")


def day_label(iso: str) -> str:
    dt = datetime.strptime(iso, "%Y-%m-%d")
    return dt.strftime("%a %-d %b")


def load_records() -> list[dict]:
    records = []
    for pf in sorted(RESULTS_DIR.glob("page_*.json")):
        with pf.open(encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("Items", []):
            pn = item.get("PaperNumber", "")
            conf = pn.split("-")[0] if "-" in pn else pn
            if conf not in CONFERENCES_OF_INTEREST:
                continue
            for entry in item.get("DateTimeLocationDataList", []):
                parsed = parse_dtl(entry.get("date_time_location", ""))
                if not parsed:
                    continue
                date_str, time_slot, room = parsed
                records.append(
                    {
                        "date_iso": date_to_iso(date_str),
                        "time_slot": time_slot,
                        "time_sort": slot_sort_key(time_slot),
                        "room": room,
                        "conf": conf,
                        "title": item.get("Title", ""),
                        "abstract": item.get("Abstract") or "",
                        "paper": pn,
                        "author": item.get("Authors", "").split(",")[0].strip(),
                        "url": item.get("URL") or "",
                    }
                )

    # Load plenary events
    plenary_file = RESULTS_DIR / "plenary.json"
    if plenary_file.exists():
        with plenary_file.open(encoding="utf-8") as f:
            data = json.load(f)
        for item in data.get("Items", []):
            for entry in item.get("DateTimeLocationDataList", []):
                parsed = parse_dtl(entry.get("date_time_location", ""))
                if not parsed:
                    continue
                date_str, time_slot, room = parsed
                records.append(
                    {
                        "date_iso": date_to_iso(date_str),
                        "time_slot": time_slot,
                        "time_sort": slot_sort_key(time_slot),
                        "room": room,
                        "conf": "PLENARY",
                        "title": item.get("Title", ""),
                        "abstract": item.get("Description") or "",
                        "paper": "",
                        "author": "",
                        "url": item.get("URL") or "",
                    }
                )

    return records


def build_schedule(records: list[dict]) -> list[dict]:
    grid: dict[str, dict[str, dict[str, list]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    sort_map: dict[str, dict[str, datetime]] = defaultdict(dict)

    for r in records:
        d, ts, room = r["date_iso"], r["time_slot"], r["room"]
        grid[d][ts][room].append(r)
        sort_map[d][ts] = r["time_sort"]

    days = []
    for date_iso in sorted(grid.keys()):
        day_grid = grid[date_iso]
        time_slots = sorted(day_grid.keys(), key=lambda s: sort_map[date_iso][s])
        rooms = sorted({rm for ts_data in day_grid.values() for rm in ts_data})

        slots_list = []
        for ts in time_slots:
            cells: dict[str, list] = {}
            for room in rooms:
                talks = day_grid[ts].get(room, [])
                if talks:
                    cells[room] = talks
            slots_list.append({"time": ts, "cells": cells})

        days.append(
            {
                "date_iso": date_iso,
                "label": day_label(date_iso),
                "rooms": rooms,
                "slots": slots_list,
            }
        )
    return days


def render_card(talk: dict) -> str:
    color = CONF_COLOR.get(talk["conf"], "#999")
    short = CONF_SHORT.get(talk["conf"], talk["conf"])
    search = e(f"{talk['title']} {talk['paper']} {talk['author']} {talk['abstract']}")
    tooltip = e(talk["abstract"] or "No abstract available.")
    href = f"https://spie.org{talk['url']}" if talk.get("url") else ""
    # Unique ID for bookmarking
    card_id = e(talk["paper"] if talk["paper"] else f"PLENARY-{talk['title']}")
    if talk["conf"] == "PLENARY":
        meta = ""
        extra_style = "background:#1a1a2e; border-left-color:#fff;"
        title_color = "color:#fff"
    else:
        meta = f'<div class="talk-meta">[{e(talk["paper"])}] {e(talk["author"])}</div>'
        extra_style = f"border-left-color:{color}"
        title_color = ""
    title_html = (
        f'<a class="talk-link" href="{e(href)}" target="_blank" rel="noopener">{e(talk["title"])}</a>'
        if href
        else e(talk["title"])
    )
    return (
        f'<div class="talk" data-search="{search}" data-id="{card_id}" title="{tooltip}" '
        f'style="{extra_style}">'
        f'<div class="talk-header">'
        f'<span class="talk-conf" style="color:{color}">{e(short)}</span>'
        f'<button class="star-btn" onclick="toggleBookmark(this)" title="Save to My Schedule">☆</button>'
        f"</div>"
        f'<div class="talk-title" style="{title_color}">'
        f"{title_html}</div>"
        f"{meta}"
        f"</div>"
    )


def render_table(day: dict) -> str:
    rooms = day["rooms"]
    header = '<th class="time-col">Time (CEST)</th>' + "".join(
        f"<th>{e(r)}</th>" for r in rooms
    )
    rows = []
    for slot in day["slots"]:
        ts = slot["time"]
        is_poster = ts.startswith("17:30")
        cls = "poster-row" if is_poster else "slot-row"
        tds = [f'<td class="time-cell">{e(ts)}</td>']
        for room in rooms:
            talks = slot["cells"].get(room, [])
            if talks:
                tds.append(
                    f'<td class="talk-cell">{"".join(render_card(t) for t in talks)}</td>'
                )
            else:
                tds.append('<td class="empty-cell"></td>')
        rows.append(f'<tr class="{cls}">{"".join(tds)}</tr>')

    return (
        '<div class="table-wrap">'
        '<table class="schedule-table">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )


CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 13px;
  background: #f0f2f5;
  color: #222;
  margin: 0;
  padding: 0;
}
/* ── Top bar ── */
.topbar {
  position: sticky;
  top: 0;
  z-index: 200;
  background: #1a1a2e;
  color: #fff;
  padding: 9px 16px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,.5);
}
.topbar h1 {
  font-size: 14px;
  font-weight: 700;
  margin: 0;
  color: #d0d8ff;
  letter-spacing: .03em;
  flex: 0 0 auto;
}
.search-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1 1 180px;
  max-width: 360px;
}
#search {
  flex: 1;
  padding: 5px 10px;
  border-radius: 4px;
  border: none;
  font-size: 13px;
  outline: none;
}
#search:focus { box-shadow: 0 0 0 2px #7eb8f7; }
#clear-btn {
  background: none;
  border: 1px solid #7eb8f7;
  color: #7eb8f7;
  border-radius: 4px;
  padding: 4px 9px;
  cursor: pointer;
  font-size: 12px;
}
#clear-btn:hover { background: rgba(126,184,247,.15); }
#match-count { font-size: 11px; color: #aaa; min-width: 80px; }
/* ── Legend ── */
.legend {
  padding: 7px 16px;
  background: #fff;
  border-bottom: 1px solid #ddd;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #444;
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}
/* ── Day tabs ── */
.tabs {
  display: flex;
  gap: 4px;
  padding: 10px 16px 0;
  background: #f0f2f5;
  flex-wrap: wrap;
}
.tab-btn {
  padding: 6px 16px;
  border: 1px solid #bbb;
  border-bottom: none;
  background: #e2e6ee;
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  font-size: 13px;
  font-weight: 500;
  color: #555;
  transition: background .12s;
}
.tab-btn:hover { background: #d0d8f8; }
.tab-btn.active {
  background: #fff;
  color: #1a1a2e;
  font-weight: 700;
  border-color: #aab;
}
/* ── Schedule body (single scroll container) ── */
#schedule-body {
  height: calc(100vh - var(--topbar-h, 44px));
  overflow: auto;
}
/* ── Tabs sticky within scroll container ── */
#schedule-body .tabs {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #f0f2f5;
}
/* ── Schedule grid ── */
.day-panel { padding: 0 16px 32px; }
.table-wrap {
  border: 1px solid #ccc;
  border-top: none;
  background: #fff;
  border-radius: 0 6px 6px 6px;
}
.schedule-table {
  border-collapse: collapse;
  width: 100%;
  min-width: 700px;
}
.schedule-table thead th {
  position: sticky;
  top: var(--tabs-h, 0px);
  background: #1a1a2e;
  color: #d0d8ff;
  padding: 7px 10px;
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  border-right: 1px solid #2c2c4e;
  white-space: nowrap;
  z-index: 10;
}
.schedule-table thead th.time-col {
  min-width: 120px;
  position: sticky;
  left: 0;
  z-index: 11;
  background: #111128;
  top: var(--tabs-h, 0px);
}
.schedule-table td {
  vertical-align: top;
  padding: 3px;
  border: 1px solid #e8eaee;
  min-width: 150px;
}
.time-cell {
  font-size: 11px;
  font-weight: 600;
  color: #555;
  white-space: nowrap;
  background: #f8f9fb;
  position: sticky;
  left: 0;
  z-index: 5;
  border-right: 2px solid #ddd !important;
  padding: 6px 8px;
}
.empty-cell { background: #fafbfc; }
.slot-row:hover .time-cell,
.slot-row:hover .empty-cell { background: #f0f4ff; }
.poster-row td { background: #fffaf2; }
.poster-row .time-cell { background: #fff3e0; color: #a05000; }
.poster-row:hover .time-cell { background: #ffe0b2; }
/* ── Talk cards ── */
.talk {
  border-left: 3px solid #999;
  padding: 4px 7px;
  margin-bottom: 3px;
  background: #fff;
  border-radius: 0 3px 3px 0;
  cursor: default;
  transition: opacity .18s;
  position: relative;
}
.talk:last-child { margin-bottom: 0; }
.talk:hover { box-shadow: 0 1px 5px rgba(0,0,0,.12); }
.talk-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 4px;
}
.talk-conf {
  display: block;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  margin-bottom: 2px;
  flex: 1;
}
/* ── Star / bookmark button ── */
.star-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
  color: #bbb;
  flex-shrink: 0;
  transition: color .15s, transform .15s;
}
.star-btn:hover { color: #f5a623; transform: scale(1.2); }
.talk.bookmarked .star-btn { color: #f5a623; }
.talk.bookmarked { box-shadow: inset 3px 0 0 #f5a623; }
.talk-title {
  font-size: 12px;
  line-height: 1.35;
  font-weight: 500;
  color: #111;
  margin-bottom: 2px;
}
.talk-meta {
  font-size: 10px;
  color: #888;
}
/* ── My Schedule mode ── */
body.my-schedule-mode .talk:not(.bookmarked) { display: none; }
body.my-schedule-mode tr.slot-row:not(:has(.bookmarked)),
body.my-schedule-mode tr.poster-row:not(:has(.bookmarked)) { display: none; }
#my-schedule-btn {
  background: none;
  border: 1px solid #f5a623;
  color: #f5a623;
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  transition: background .15s;
}
#my-schedule-btn:hover { background: rgba(245,166,35,.15); }
#my-schedule-btn.active { background: #f5a623; color: #1a1a2e; }
#bookmark-count { font-size: 11px; color: #f5a623; min-width: 60px; }
#share-btn {
  background: none;
  border: 1px solid #7eb8f7;
  color: #7eb8f7;
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}
#share-btn:hover { background: rgba(126,184,247,.15); }
/* ── Export/import modal ── */
.modal-backdrop {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.55);
  z-index: 1000;
  align-items: center;
  justify-content: center;
}
.modal-backdrop.open { display: flex; }
.modal {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  width: min(420px, 90vw);
  box-shadow: 0 8px 32px rgba(0,0,0,.35);
}
.modal h2 { margin: 0 0 8px; font-size: 15px; color: #1a1a2e; }
.modal p { margin: 0 0 12px; font-size: 12px; color: #555; line-height: 1.5; }
.modal textarea {
  width: 100%;
  height: 80px;
  font-family: monospace;
  font-size: 11px;
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 6px;
  resize: vertical;
  box-sizing: border-box;
}
.modal-row { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
.modal-btn {
  padding: 6px 14px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
}
.modal-btn.primary { background: #f5a623; color: #1a1a2e; }
.modal-btn.primary:hover { background: #e09510; }
.modal-btn.secondary { background: #e2e6ee; color: #333; }
.modal-btn.secondary:hover { background: #d0d8f8; }
.modal-btn.danger { background: #e15759; color: #fff; }
.modal-btn.danger:hover { background: #c0393b; }
.modal-notice { font-size: 11px; color: #3aaa8c; margin-top: 6px; min-height: 16px; }
/* ── Talk links ── */
a.talk-link {
  color: inherit;
  text-decoration: none;
}
a.talk-link:hover { text-decoration: underline; }
/* ── Search states ── */
.talk.dim { opacity: 0.07; pointer-events: none; }
.talk.match { box-shadow: 0 0 0 2px #f5a623; }
tr.hidden-row { display: none; }
"""

JS = """
const LS_KEY = 'spie_as26_bookmarks';
let bookmarks = new Set(JSON.parse(localStorage.getItem(LS_KEY) || '[]'));
let myScheduleActive = false;

function saveBookmarks() {
  localStorage.setItem(LS_KEY, JSON.stringify([...bookmarks]));
  updateBookmarkCount();
}

function updateBookmarkCount() {
  const n = bookmarks.size;
  document.getElementById('bookmark-count').textContent =
    n ? n + ' saved' : '';
}

function toggleBookmark(btn) {
  const card = btn.closest('.talk');
  const id = card.dataset.id;
  if (bookmarks.has(id)) {
    bookmarks.delete(id);
    card.classList.remove('bookmarked');
    btn.textContent = '\u2606';
  } else {
    bookmarks.add(id);
    card.classList.add('bookmarked');
    btn.textContent = '\u2605';
  }
  saveBookmarks();
  if (myScheduleActive) applyMySchedule();
}

function restoreBookmarks() {
  document.querySelectorAll('.talk').forEach(card => {
    if (bookmarks.has(card.dataset.id)) {
      card.classList.add('bookmarked');
      card.querySelector('.star-btn').textContent = '\u2605';
    }
  });
}

function applyMySchedule() {
  // :has() handles row hiding via CSS; just ensure hidden-row doesn't conflict
  document.querySelectorAll('tr.hidden-row').forEach(r => {
    r.classList.toggle('hidden-row', !myScheduleActive);
  });
}

function toggleMySchedule() {
  myScheduleActive = !myScheduleActive;
  document.body.classList.toggle('my-schedule-mode', myScheduleActive);
  const btn = document.getElementById('my-schedule-btn');
  btn.classList.toggle('active', myScheduleActive);
  btn.textContent = myScheduleActive ? '\u2605 All talks' : '\u2605 My Schedule';
  // Clear search when entering My Schedule mode
  if (myScheduleActive) {
    document.getElementById('search').value = '';
    document.querySelectorAll('.talk').forEach(t => t.classList.remove('dim', 'match'));
    document.querySelectorAll('tr').forEach(r => r.classList.remove('hidden-row'));
    document.getElementById('match-count').textContent = '';
  }
}

function switchDay(iso) {
  document.querySelectorAll('.day-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('day-' + iso).style.display = 'block';
  document.querySelector('[data-day="' + iso + '"]').classList.add('active');
  applySearch();
}

function applySearch() {
  const q = document.getElementById('search').value.toLowerCase().trim();
  const panel = document.querySelector('.day-panel[style*="block"]');
  if (!panel) return;
  let n = 0;
  panel.querySelectorAll('.talk').forEach(t => {
    const text = t.dataset.search.toLowerCase();
    if (!q) {
      t.classList.remove('dim', 'match');
    } else if (text.includes(q)) {
      t.classList.remove('dim');
      t.classList.add('match');
      n++;
    } else {
      t.classList.add('dim');
      t.classList.remove('match');
    }
  });
  panel.querySelectorAll('tr.slot-row, tr.poster-row').forEach(row => {
    row.classList.toggle('hidden-row', q && !row.querySelector('.talk.match'));
  });
  document.getElementById('match-count').textContent =
    q ? n + ' match' + (n !== 1 ? 'es' : '') : '';
}

function clearSearch() {
  document.getElementById('search').value = '';
  applySearch();
}

document.getElementById('search').addEventListener('input', () => {
  if (myScheduleActive) toggleMySchedule(); // exit My Schedule mode on search
  applySearch();
});
document.getElementById('search').addEventListener('keydown', ev => {
  if (ev.key === 'Escape') clearSearch();
});

function updateStickyOffset() {
  const topbarH = document.querySelector('.topbar').offsetHeight;
  document.documentElement.style.setProperty('--topbar-h', topbarH + 'px');
  const tabsEl = document.querySelector('#schedule-body .tabs');
  if (tabsEl) {
    document.documentElement.style.setProperty('--tabs-h', tabsEl.offsetHeight + 'px');
  }
  const body = document.getElementById('schedule-body');
  if (body) body.style.height = (window.innerHeight - topbarH) + 'px';
}
updateStickyOffset();
window.addEventListener('resize', updateStickyOffset);

restoreBookmarks();
updateBookmarkCount();

// ── Export / Import ──
function encodeBookmarks() {
  return JSON.stringify([...bookmarks], null, 2);
}

function openShareModal() {
  document.getElementById('export-code').value = encodeBookmarks() || '';
  document.getElementById('import-code').value = '';
  document.getElementById('share-notice').textContent = '';
  document.getElementById('share-modal').classList.add('open');
}

function closeShareModal() {
  document.getElementById('share-modal').classList.remove('open');
}

function copyExport() {
  const ta = document.getElementById('export-code');
  if (!ta.value) {
    document.getElementById('share-notice').textContent = 'No bookmarks to export.';
    return;
  }
  navigator.clipboard.writeText(ta.value).then(() => {
    document.getElementById('share-notice').textContent = 'Copied to clipboard!';
  });
}

function importBookmarks() {
  const raw = document.getElementById('import-code').value.trim();
  if (!raw) {
    document.getElementById('share-notice').textContent = 'Paste a code first.';
    return;
  }
  try {
    const ids = JSON.parse(raw);
    if (!Array.isArray(ids)) throw new Error();
    bookmarks = new Set(ids);
    saveBookmarks();
    restoreBookmarks();
    document.getElementById('share-notice').textContent =
      ids.length + ' bookmark' + (ids.length !== 1 ? 's' : '') + ' imported.';
  } catch {
    document.getElementById('share-notice').textContent = 'Invalid code — please try again.';
  }
}

function clearAllBookmarks() {
  if (!confirm('Remove all saved talks?')) return;
  bookmarks = new Set();
  saveBookmarks();
  document.querySelectorAll('.talk.bookmarked').forEach(c => {
    c.classList.remove('bookmarked');
    c.querySelector('.star-btn').textContent = '\u2606';
  });
  document.getElementById('export-code').value = '';
  document.getElementById('share-notice').textContent = 'All bookmarks cleared.';
}

document.getElementById('share-modal').addEventListener('click', ev => {
  if (ev.target === ev.currentTarget) closeShareModal();
});
"""


def build_html(days: list[dict]) -> str:
    legend = "".join(
        f'<span class="legend-item">'
        f'<span class="legend-dot" style="background:{CONF_COLOR.get(c, "#999")}"></span>'
        f"{e(CONF_SHORT.get(c, c))}</span>"
        for c in sorted(CONF_SHORT)
    )

    tabs = "".join(
        f'<button class="tab-btn{" active" if i == 0 else ""}" '
        f'data-day="{d["date_iso"]}" onclick="switchDay(\'{d["date_iso"]}\')">'
        f"{e(d['label'])}</button>"
        for i, d in enumerate(days)
    )

    panels = "".join(
        f'<div class="day-panel" id="day-{d["date_iso"]}" '
        f'style="display:{"block" if i == 0 else "none"}">'
        f"{render_table(d)}</div>"
        for i, d in enumerate(days)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SPIE AS26 · Schedule</title>
<style>{CSS}</style>
</head>
<body>

<div class="topbar">
  <h1>SPIE AS26 · Schedule</h1>
  <div class="search-wrap">
    <input id="search" type="search" placeholder="Search title, author, paper #, keyword…" autocomplete="off">
    <button id="clear-btn" onclick="clearSearch()">Clear</button>
  </div>
  <button id="my-schedule-btn" onclick="toggleMySchedule()">&#9733; My Schedule</button>
  <span id="bookmark-count"></span>
  <button id="share-btn" onclick="openShareModal()">&#8645; Export / Import</button>
  <span id="match-count"></span>
</div>

<div class="legend">{legend}</div>
<div id="schedule-body">
<div class="tabs">{tabs}</div>
{panels}
</div>

<div class="modal-backdrop" id="share-modal">
  <div class="modal">
    <h2>&#8645; Export / Import bookmarks</h2>
    <p>Copy the code below and paste it on another device to transfer your saved talks.</p>
    <label style="font-size:11px;font-weight:600;color:#555">Your code</label>
    <textarea id="export-code" readonly placeholder="(no bookmarks saved yet)"></textarea>
    <div class="modal-row">
      <button class="modal-btn primary" onclick="copyExport()">Copy to clipboard</button>
      <button class="modal-btn danger" onclick="clearAllBookmarks()">Clear all</button>
      <button class="modal-btn secondary" onclick="closeShareModal()">Close</button>
    </div>
    <p style="margin-top:16px;margin-bottom:4px">Paste a code from another device:</p>
    <textarea id="import-code" placeholder="Paste code here…"></textarea>
    <div class="modal-row">
      <button class="modal-btn primary" onclick="importBookmarks()">Import</button>
    </div>
    <div class="modal-notice" id="share-notice"></div>
  </div>
</div>

<script>{JS}</script>
</body>
</html>
"""


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    print("Loading records…")
    records = load_records()
    print(
        f"  {len(records)} records across {len(CONFERENCES_OF_INTEREST)} conferences."
    )
    days = build_schedule(records)
    html = build_html(days)
    out = OUTPUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Written → {out}")
    for d in days:
        print(f"  {d['label']}: {len(d['slots'])} time slots, {len(d['rooms'])} rooms")


if __name__ == "__main__":
    main()
