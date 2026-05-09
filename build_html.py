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

PX_MIN = 4  # pixels per minute of conference time
ROOM_COL_W = 180  # pixels per room column

POSTER_START_MIN = 17 * 60 + 30  # 17:30 in minutes from midnight
POSTER_END_MIN = 19 * 60  # 19:00

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
    "PLENARY": "#9467bd",
}

SYNC_API_URL = "https://spie-sync.peterpihlmannpedersen-cloudflare.workers.dev"  # e.g. "https://spie-sync.yourname.workers.dev"

TINDER_SVG = (
    '<svg width="13" height="13" viewBox="0 0 512 512"'
    ' style="vertical-align:-1px;margin-right:4px"'
    ' xmlns="http://www.w3.org/2000/svg">'
    '<path fill="#FF6647" d="M379.663,107.423C341.154,55.603,296.385,23.775,274.87,8.48'
    "c-2.876-2.045-5.711-4.149-8.592-6.184c-2.314-1.635-4.832-2.737-7.712-2.124"
    "c-4.877,1.038-8,6.313-6.511,11.081c21.208,67.867,8.505,133.558-40.027,205.744"
    "c-13.849-28.726-21.115-55.53-21.115-78.159c0-5.216-4.78-9.347-9.945-8.585"
    "c-2.525,0.373-4.193,1.883-6.052,3.47c-2.149,1.833-4.363,3.591-6.564,5.361"
    "c-29.431,23.681-107.611,86.582-107.611,190.674c0,48.29,20.572,94.126,57.925,129.065"
    "c36.128,33.794,84.603,53.177,132.995,53.177c63.426,0,115.435-18.456,150.406-53.373"
    'c32.182-32.13,49.192-76.692,49.192-128.869C451.259,246.159,427.17,171.355,379.663,107.423z"/>'
    '<path fill="#E35336" d="M153.378,458.824c-37.354-34.941-57.925-80.777-57.925-129.065'
    "c0-92.296,61.46-152.202,95.907-181.104c-0.286-3.348-0.447-6.627-0.447-9.816"
    "c0-5.216-4.78-9.349-9.945-8.585c-2.525,0.373-4.193,1.883-6.053,3.47"
    "c-2.149,1.833-4.363,3.591-6.564,5.361C138.92,162.765,60.74,225.667,60.74,329.758"
    "c0,48.29,20.572,94.126,57.925,129.065C154.794,492.618,203.268,512,251.661,512"
    'c6.702,0,13.268-0.219,19.708-0.628C228.085,507.824,185.769,489.122,153.378,458.824z"/>'
    "</svg>"
)

UNDO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"'
    ' width="22" height="22" style="display:block">'
    '<path fill-rule="evenodd" d="M9.53 2.47a.75.75 0 0 1 0 1.06L4.81 8.25H15a6.75 6.75 0 0 1 0'
    " 13.5h-3a.75.75 0 0 1 0-1.5h3a5.25 5.25 0 1 0 0-10.5H4.81l4.72 4.72a.75.75 0 1 1-1.06"
    ' 1.06l-6-6a.75.75 0 0 1 0-1.06l6-6a.75.75 0 0 1 1.06 0Z" clip-rule="evenodd"/>'
    "</svg>"
)

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


def slot_end(ts: str) -> str:
    """Return end time 'HH:MM' from 'HH:MM - HH:MM CEST', or '' if unparseable."""
    parts = ts.split(" - ")
    if len(parts) < 2:
        return ""
    return parts[1].split()[0]


def to_minutes(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def talk_time_bounds(r: dict) -> tuple[int, int]:
    """Return (start_min, end_min) for a record."""
    s = to_minutes(r["time_sort"])
    end_str = slot_end(r["time_slot"])
    if end_str:
        try:
            return s, to_minutes(datetime.strptime(end_str, "%H:%M"))
        except ValueError:
            pass
    return s, s + 20


def day_label(iso: str) -> str:
    dt = datetime.strptime(iso, "%Y-%m-%d")
    return dt.strftime("%a %-d %b")


def is_poster(r: dict) -> bool:
    """True if the record is a 17:30–19:00 poster session entry."""
    return r["time_slot"].startswith("17:30") and "19:00" in r["time_slot"]


def build_poster_days(records: list[dict]) -> list[dict]:
    """Return per-day poster data grouped by conference."""
    by_day: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        if not is_poster(r):
            continue
        by_day[r["date_iso"]][r["conf"]].append(r)

    days = []
    for date_iso in sorted(by_day.keys()):
        confs_map = by_day[date_iso]
        days.append(
            {
                "date_iso": date_iso,
                "label": day_label(date_iso),
                "confs_map": {
                    conf: sorted(confs_map[conf], key=lambda r: r["title"])
                    for conf in sorted(confs_map.keys())
                },
            }
        )
    return days


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
                        "authors": item.get("Authors", "").strip(),
                        "url": item.get("URL") or "",
                    }
                )

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
                        "authors": "",
                        "url": item.get("URL") or "",
                    }
                )

    return records


def serialize_talk(t: dict) -> dict:
    """Compact JSON-serializable form of a talk record (no datetime objects)."""
    return {
        "conf": t["conf"],
        "title": t["title"],
        "paper": t["paper"],
        "author": t["author"],
        "room": t["room"],
        "start_min": to_minutes(t["time_sort"]),
        "end_str": slot_end(t["time_slot"]),
        "url": t.get("url") or "",
    }


def serialize_days(days: list[dict]) -> list:
    return [
        {
            "date_iso": d["date_iso"],
            "label": d["label"],
            "rooms": d["rooms"],
            "day_start_min": d["day_start_min"],
            "day_end_min": d["day_end_min"],
            "rooms_map": {
                room: [serialize_talk(t) for t in talks]
                for room, talks in d["rooms_map"].items()
            },
        }
        for d in days
    ]


def serialize_poster_days(poster_days: list[dict]) -> list:
    return [
        {
            "date_iso": d["date_iso"],
            "label": d["label"],
            "confs_map": {
                conf: [serialize_talk(t) for t in talks]
                for conf, talks in d["confs_map"].items()
            },
        }
        for d in poster_days
    ]


def build_talk_data(records: list[dict]) -> dict:
    """Map card-id → {abstract, authors} for the single JS TALK_DATA lookup table."""
    data: dict[str, dict] = {}
    for r in records:
        key = r["paper"] if r["paper"] else f"PLENARY-{r['title']}"
        if key not in data:
            data[key] = {
                "abstract": r.get("abstract") or "",
                "authors": r.get("authors") or "",
            }
    return data


def build_days(records: list[dict]) -> list[dict]:
    by_day: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        if is_poster(r):
            continue
        by_day[r["date_iso"]][r["room"]].append(r)

    days = []
    for date_iso in sorted(by_day.keys()):
        rooms_map = by_day[date_iso]
        rooms = sorted(rooms_map.keys())

        all_starts, all_ends = [], []
        for rm_talks in rooms_map.values():
            for r in rm_talks:
                s = to_minutes(r["time_sort"])
                all_starts.append(s)
                end_str = slot_end(r["time_slot"])
                if end_str:
                    try:
                        all_ends.append(to_minutes(datetime.strptime(end_str, "%H:%M")))
                    except ValueError:
                        all_ends.append(s + 20)
                else:
                    all_ends.append(s + 20)

        day_start = (min(all_starts) // 30) * 30
        day_end = ((max(all_ends) + 29) // 30) * 30

        days.append(
            {
                "date_iso": date_iso,
                "label": day_label(date_iso),
                "rooms": rooms,
                "rooms_map": {
                    rm: sorted(rooms_map[rm], key=lambda r: r["time_sort"])
                    for rm in rooms
                },
                "day_start_min": day_start,
                "day_end_min": day_end,
            }
        )
    return days


def _modal_data(talk: dict, href: str, short: str, color: str) -> str:
    """Returns data-* attribute string carrying everything the talk modal needs."""
    end_str = slot_end(talk["time_slot"])
    start_min = to_minutes(talk["time_sort"])
    time_str = f"{start_min // 60:02d}:{start_min % 60:02d}"
    time_label = f"{time_str}–{end_str} CEST" if end_str else time_str
    return (
        f'data-title="{e(talk["title"])}" '
        f'data-paper="{e(talk["paper"])}" '
        f'data-author="{e(talk["author"])}" '
        f'data-url="{e(href)}" '
        f'data-conf="{e(talk["conf"])}" '
        f'data-short="{e(short)}" '
        f'data-color="{color}" '
        f'data-time="{e(time_label)}" '
        f'data-room="{e(talk["room"])}"'
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
  cursor: pointer;
  user-select: none;
  transition: opacity .15s;
  border-radius: 4px;
  padding: 2px 4px;
}
.legend-item:hover { opacity: 0.7; }
.legend-item.inactive { opacity: 0.2; }
#clear-conf-btn {
  background: none;
  border: 1px solid #bbb;
  color: #666;
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  font-size: 11px;
  margin-left: 4px;
}
#clear-conf-btn:hover { border-color: #e15759; color: #e15759; }
.conf-hidden { display: none !important; }
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
/* ── Day panel ── */
.day-panel { padding-bottom: 32px; }
/* ── Calendar grid ── */
.cal-wrap { background: #f0f2f5; }
.cal-header-row {
  display: flex;
  position: sticky;
  top: var(--tabs-h, 0);
  z-index: 12;
  background: #1a1a2e;
  min-width: fit-content;
  border-bottom: 1px solid #2c2c4e;
}
.cal-gutter-ph {
  width: 52px;
  flex-shrink: 0;
  border-right: 1px solid #2c2c4e;
}
.cal-room-head {
  width: 180px;
  flex-shrink: 0;
  padding: 6px 8px;
  font-size: 11px;
  font-weight: 600;
  color: #d0d8ff;
  border-right: 1px solid #2c2c4e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cal-body {
  display: flex;
  min-width: fit-content;
}
.cal-gutter {
  width: 52px;
  flex-shrink: 0;
  position: sticky;
  left: 0;
  z-index: 11;
  background: #f0f2f5;
  border-right: 1px solid #ccc;
}
.cal-mark {
  position: absolute;
  right: 5px;
  font-size: 9px;
  color: #888;
  font-weight: 600;
  transform: translateY(-50%);
  white-space: nowrap;
  user-select: none;
}
.cal-mark.first-mark {
  transform: none;
  top: 4px !important;
}
.cal-timeline {
  position: relative;
  flex-shrink: 0;
  background: #fff;
}
.cal-hour-line {
  position: absolute;
  left: 0; right: 0;
  border-top: 1px solid #dde0e6;
  z-index: 1;
  pointer-events: none;
}
.cal-half-line {
  position: absolute;
  left: 0; right: 0;
  border-top: 1px dashed #eaecf0;
  z-index: 1;
  pointer-events: none;
}
.cal-poster-band {
  position: absolute;
  left: 0; right: 0;
  background: rgba(255, 243, 220, 0.6);
  z-index: 1;
  pointer-events: none;
}
.cal-cols {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  z-index: 2;
}
.cal-col {
  width: 180px;
  flex-shrink: 0;
  position: relative;
  border-right: 1px solid #e0e2e8;
}
/* ── Session blocks (concurrent talks, e.g. poster sessions) ── */
.cal-session {
  position: absolute;
  left: 2px; right: 2px;
  display: flex;
  flex-direction: column;
  border-left: 3px solid #888;
  border-top: 1px solid #e0e2e8;
  border-bottom: 1px solid #e0e2e8;
  border-right: 1px solid #e0e2e8;
  border-radius: 0 3px 3px 0;
  background: #fff;
  overflow: hidden;
}
.session-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: #f0f2f5;
  border-bottom: 1px solid #dde0e6;
  font-size: 10px;
  font-weight: 700;
  color: #555;
  flex-shrink: 0;
  white-space: nowrap;
  gap: 8px;
}
.session-list {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}
.session-item {
  border-radius: 0;
  border-bottom: 1px solid #f0f2f5;
  margin: 0;
}
.session-item:last-child { border-bottom: none; }
/* ── Talk cards ── */
.talk {
  border-left: 3px solid #999;
  padding: 4px 6px;
  background: #fff;
  border-radius: 0 3px 3px 0;
  cursor: default;
  transition: opacity .18s;
}
.talk:hover { box-shadow: 0 2px 8px rgba(0,0,0,.15); z-index: 5; }
.cal-talk {
  position: absolute;
  left: 2px; right: 2px;
  overflow: hidden;
  border-top: 1px solid #e0e2e8;
  border-bottom: 1px solid #e0e2e8;
  border-right: 1px solid #e0e2e8;
}
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
  margin-bottom: 1px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  font-size: 11px;
  line-height: 1.3;
  font-weight: 500;
  color: #111;
  margin-bottom: 1px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}
.talk-meta {
  font-size: 10px;
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* ── My Schedule mode ── */
body.my-schedule-mode .talk:not(.bookmarked) { display: none; }
#my-schedule-btn {
  background: none;
  border: 1px solid #556;
  color: #aab;
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  min-width: 120px;
  transition: background .15s, border-color .15s, color .15s;
}
#my-schedule-btn:hover { border-color: #f5a623; color: #f5a623; }
#my-schedule-btn.active { background: #f5a623; color: #1a1a2e; border-color: #f5a623; }
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
.talk-link {
  color: inherit;
  text-decoration: none;
  cursor: pointer;
}
.talk-link:hover { text-decoration: underline; }
/* ── Talk detail modal ── */
#talk-modal .modal { max-width: 640px; max-height: 90vh; overflow-y: auto; position: relative; }
.modal-close {
  position: absolute;
  top: 12px;
  right: 12px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  color: #888;
  line-height: 1;
  padding: 4px 6px;
  border-radius: 4px;
}
.modal-close:hover { background: #f0f0f0; color: #333; }
#talk-modal-conf {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .03em;
  text-transform: uppercase;
  margin-bottom: 6px;
  display: block;
}
#talk-modal h2 {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.4;
  margin: 0 0 8px;
  padding-right: 32px;
}
#talk-modal-meta {
  font-size: 12px;
  color: #666;
  margin: 0 0 14px;
}
#talk-modal-abstract {
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  margin: 0 0 16px;
  color: #333;
}
#talk-modal-ext {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #7eb8f7;
  text-decoration: none;
}
#talk-modal-ext:hover { text-decoration: underline; }
/* ── Search states ── */
.talk.dim { opacity: 0.07; pointer-events: none; }
.talk.match { box-shadow: 0 0 0 2px #f5a623 !important; }
/* ── Agenda view (mobile calendar) ── */
.cal-agenda { display: none; background: #fff; }
.agenda-hour-sep {
  position: sticky;
  z-index: 5;
  display: flex;
  align-items: center;
  padding: 0 14px;
  height: 28px;
  background: #f0f2f5;
  border-top: 1px solid #dde0e6;
  border-bottom: 1px solid #dde0e6;
}
.agenda-hour-sep span {
  font-size: 11px;
  font-weight: 700;
  color: #777;
  letter-spacing: .06em;
}
.agenda-row {
  display: flex;
  align-items: flex-start;
  border-left: 3px solid #999;
  border-bottom: 1px solid #f0f2f5;
  background: #fff;
  padding: 10px 6px 10px 0;
  min-height: 54px;
  transition: background .1s;
  cursor: default;
}
.agenda-row:hover { background: #f7f9ff; }
.agenda-row.bookmarked { box-shadow: inset 3px 0 0 #f5a623, 0 0 0 0 transparent; }
.agenda-row--plenary { background: #0d0d1e; }
.agenda-row--plenary:hover { background: #131326; }
.agenda-row--plenary .agenda-title { color: #d0d8ff; }
.agenda-row--plenary .agenda-meta  { color: #7a82aa; }
.agenda-time-col {
  width: 58px;
  flex-shrink: 0;
  padding: 2px 10px 0;
  text-align: right;
}
.agenda-time-start {
  font-size: 12px;
  font-weight: 600;
  color: #555;
  display: block;
  line-height: 1.25;
}
.agenda-time-end {
  font-size: 10px;
  color: #aaa;
  display: block;
  line-height: 1.25;
}
.agenda-event-col {
  flex: 1;
  min-width: 0;
  padding-right: 4px;
}
.agenda-conf {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  display: block;
  margin-bottom: 2px;
}
.agenda-title {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.35;
  color: #111;
  margin-bottom: 3px;
}
.agenda-meta {
  font-size: 11px;
  color: #888;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* ── Top-level view switcher ── */
.view-nav {
  display: flex;
  gap: 0;
  background: #1a1a2e;
  border-bottom: 1px solid #2c2c4e;
  padding: 0 16px;
}
.view-btn {
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  color: #aab;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 16px;
  cursor: pointer;
  transition: color .12s, border-color .12s;
  white-space: nowrap;
}
.view-btn:hover { color: #d0d8ff; }
.view-btn.active { color: #fff; border-bottom-color: #7eb8f7; }
.view-nav-toggle {
  display: none;
}
.view-nav-divider {
  width: 1px;
  background: #2c2c4e;
  margin: 6px 4px;
  align-self: stretch;
}
/* ── Page containers ── */
.page { display: none; }
.page.active { display: block; }
/* ── Poster page ── */
#poster-body {
  height: calc(100vh - var(--topbar-h, 44px));
  overflow-y: auto;
  padding: 0 0 32px;
}
#poster-body .tabs {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #f0f2f5;
  padding: 10px 16px 0;
}
#poster-star-count, #talklist-star-count { font-size: 11px; color: #f5a623; padding: 4px 16px 6px; display: block; }
/* ── Poster panels & items ── */
.poster-day-panel { display: none; padding: 16px; }
.poster-day-panel.active { display: block; }
.poster-item-conf {
  font-weight: 700;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.poster-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid #f0f2f5;
  transition: background .1s;
}
.poster-item:last-child { border-bottom: none; }
.poster-item:hover { background: #fafafa; }
.poster-item.bookmarked { box-shadow: inset 3px 0 0 #f5a623; }
.poster-item.skipped { opacity: 0.35; }
.poster-item-body { flex: 1; min-width: 0; }
.poster-item-title {
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
  color: #111;
}
.poster-item-title a { color: inherit; text-decoration: none; }
.poster-item-title a:hover { text-decoration: underline; }
.poster-item-meta {
  font-size: 10px;
  color: #888;
  margin-top: 2px;
}
.poster-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  align-items: center;
}
.poster-star-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  color: #bbb;
  padding: 0;
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color .15s, transform .15s;
}
.poster-star-btn:hover { color: #f5a623; transform: scale(1.15); }
.poster-item.bookmarked .poster-star-btn { color: #f5a623; }
.poster-skip-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  color: #bbb;
  padding: 0;
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color .15s;
}
.poster-skip-btn:hover { color: #e15759; }
.poster-item.skipped .poster-skip-btn { color: #e15759; }
/* ── Talk list ── */
#talklist-body {
  height: calc(100vh - var(--topbar-h, 44px));
  overflow-y: auto;
  padding: 0 0 32px;
}
#talklist-body .tabs {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #f0f2f5;
  padding: 10px 16px 0;
}
.talk-list-day-panel { display: none; padding: 0 16px 16px; }
.talk-list-day-panel.active { display: block; }
.talk-list-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 4px;
  border-bottom: 1px solid #eee;
}
.talk-list-item:last-child { border-bottom: none; }
.talk-list-item:hover { background: #fafafa; }
.talk-list-item.bookmarked { box-shadow: inset 3px 0 0 #f5a623; }
.talk-list-item.bookmarked .star-btn { color: #f5a623; }
.talk-list-item.skipped { opacity: 0.35; }
.talk-list-item.skipped .talk-skip-btn { color: #e15759; }
.talk-skip-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: #bbb;
  padding: 0 2px;
  flex-shrink: 0;
  transition: color .15s;
}
.talk-skip-btn:hover { color: #e15759; }
.talk-list-time {
  font-size: 11px;
  color: #666;
  white-space: nowrap;
  min-width: 120px;
  padding-top: 2px;
}
.talk-list-body { flex: 1; min-width: 0; }
.talk-list-conf { font-size: 11px; font-weight: 600; }
.talk-list-title {
  font-size: 13px;
  font-weight: 500;
  margin: 2px 0;
}
.talk-list-title a { color: inherit; text-decoration: none; }
.talk-list-title a:hover { text-decoration: underline; }
.talk-list-meta { font-size: 11px; color: #666; }
/* ── Swipe game ── */
#swipe-body, #talkswipe-body {
  height: calc(100vh - var(--topbar-h, 44px));
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #0e0e1c;
  overflow: hidden;
}
.swipe-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  width: 100%;
  background: #1a1a2e;
  border-bottom: 1px solid #2c2c4e;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.swipe-filter-label {
  font-size: 12px;
  color: #aab;
  white-space: nowrap;
}
.swipe-filter-select {
  background: #0e0e1c;
  color: #d0d8ff;
  border: 1px solid #2c2c4e;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
}
.swipe-counter {
  font-size: 12px;
  color: #aab;
  margin-left: auto;
}
.swipe-reset-btn {
  background: none;
  border: 1px solid #aab;
  color: #aab;
  border-radius: 4px;
  padding: 3px 10px;
  cursor: pointer;
  font-size: 11px;
}
.swipe-reset-btn:hover { border-color: #fff; color: #fff; }
.swipe-arena {
  flex: 1;
  width: 100%;
  max-width: 520px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 20px 16px;
}
.swipe-card {
  position: absolute;
  width: calc(100% - 32px);
  max-width: 480px;
  background: #1a1a2e;
  border: 1px solid #2c2c4e;
  border-radius: 12px;
  padding: 20px 20px 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,.6);
  cursor: grab;
  user-select: none;
  will-change: transform;
  transition: box-shadow .15s;
  touch-action: none;
}
.swipe-card:active { cursor: grabbing; }
.swipe-card.dragging { transition: none; }
.swipe-card.fly-left  { transition: transform .35s ease-in, opacity .35s; transform: translateX(-140%) rotate(-18deg) !important; opacity: 0; pointer-events: none; }
.swipe-card.fly-right { transition: transform .35s ease-in, opacity .35s; transform: translateX(140%) rotate(18deg) !important; opacity: 0; pointer-events: none; }
.swipe-card.fly-up    { transition: transform .35s ease-in, opacity .35s; transform: translateY(-120%) !important; opacity: 0; pointer-events: none; }
.swipe-hint-skip {
  position: absolute;
  top: 16px; left: 16px;
  background: rgba(225,87,89,.85);
  color: #fff;
  font-weight: 700;
  font-size: 18px;
  padding: 4px 12px;
  border-radius: 6px;
  opacity: 0;
  transition: opacity .12s;
  pointer-events: none;
  transform: rotate(-10deg);
}
.swipe-hint-save {
  position: absolute;
  top: 16px; right: 16px;
  background: rgba(245,166,35,.85);
  color: #1a1a2e;
  font-weight: 700;
  font-size: 18px;
  padding: 4px 12px;
  border-radius: 6px;
  opacity: 0;
  transition: opacity .12s;
  pointer-events: none;
  transform: rotate(10deg);
}
.swipe-card-conf {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  margin-bottom: 8px;
}
.swipe-card-title {
  font-size: 15px;
  font-weight: 600;
  color: #e8ecff;
  line-height: 1.4;
  margin-bottom: 8px;
}
.swipe-card-title a { color: inherit; text-decoration: none; }
.swipe-card-title a:hover { text-decoration: underline; }
.swipe-card-meta {
  font-size: 11px;
  color: #7a82aa;
  margin-bottom: 10px;
}
.swipe-card-abstract {
  font-size: 12px;
  color: #9da5c8;
  line-height: 1.5;
  max-height: 160px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.swipe-btn-row {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 12px 0 16px;
  flex-shrink: 0;
  width: 100%;
  max-width: 520px;
}
.swipe-action-btn {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  border: 2px solid;
  background: #1a1a2e;
  font-size: 26px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform .12s, background .12s;
  flex-shrink: 0;
}
.swipe-action-btn:hover { transform: scale(1.12); }
.swipe-action-btn.skip-btn  { border-color: #e15759; color: #e15759; }
.swipe-action-btn.skip-btn:hover  { background: rgba(225,87,89,.15); }
.swipe-action-btn.save-btn  { border-color: #f5a623; color: #f5a623; }
.swipe-action-btn.save-btn:hover  { background: rgba(245,166,35,.15); }
.swipe-action-btn.undo-btn  { width: 50px; height: 50px; border-color: #7eb8f7; color: #7eb8f7; }
.swipe-action-btn.undo-btn:hover  { background: rgba(126,184,247,.15); }
.swipe-done {
  color: #aab;
  text-align: center;
  padding: 40px 20px;
  font-size: 14px;
  line-height: 1.8;
}
.swipe-done strong { color: #d0d8ff; }
.swipe-keys {
  font-size: 11px;
  color: #555;
  text-align: center;
  padding: 4px 0 8px;
  flex-shrink: 0;
}
/* ── Mobile ── */
@media (max-width: 680px) {
  body { font-size: 14px; }
  .topbar { padding: 8px 12px; gap: 6px; }
  .topbar h1 { display: none; }
  .search-wrap { max-width: unset; flex: 1 1 auto; }
  #search { font-size: 16px; }
  .legend { display: none; }
  .view-nav { padding: 0; flex-wrap: wrap; position: relative; }
  .view-btn { display: none; font-size: 13px; padding: 11px 20px; width: 100%; text-align: left; border-bottom: none; border-top: 1px solid #2c2c4e; }
  .view-btn.active { border-bottom: none; border-left: 3px solid #7eb8f7; }
  .view-nav.open .view-btn { display: block; }
  .view-nav-divider { display: none; }
  .view-nav.open .view-nav-divider { display: block; width: 100%; height: 1px; margin: 0; background: #3a3a5e; }
  .view-nav-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    background: none;
    border: none;
    color: #d0d8ff;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 16px;
    cursor: pointer;
  }
  .view-nav-arrow { font-size: 10px; color: #7eb8f7; transition: transform .15s; }
  .view-nav.open .view-nav-arrow { transform: rotate(180deg); }
  .tabs { padding: 6px 10px 0; gap: 3px; }
  .tab-btn { padding: 7px 12px; font-size: 12px; }
  /* Calendar: hide grid, show agenda */
  .cal-wrap { display: none; }
  .cal-agenda { display: block; }
  .agenda-title { font-size: 14px; }
  .agenda-meta { font-size: 12px; }
  .star-btn { font-size: 20px; min-height: 44px; min-width: 44px; padding: 0 6px; }
  /* Swipe */
  .swipe-card { padding: 14px 14px 12px; }
  .swipe-card-title { font-size: 14px; }
  .swipe-card-abstract { max-height: 100px; font-size: 12px; }
  .swipe-action-btn { width: 54px; height: 54px; font-size: 22px; }
  .swipe-action-btn.undo-btn { width: 44px; height: 44px; font-size: 19px; }
  .swipe-keys { display: none; }
  .swipe-btn-row { gap: 20px; }
}
"""

RENDER_JS = """
// ── Lazy-rendering helpers ──────────────────────────────────────────────────
// Track which views have been built so we only render once.
const _builtScheduleDays = new Set();
let _talkListBuilt = false;
let _posterBuilt   = false;

function he(s) {
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function _talkId(t) { return t.paper || ('PLENARY-' + t.title); }
function _talkHref(t) { return t.url ? 'https://spie.org' + t.url : ''; }

function _modalAttrs(t, dayLabel='') {
  const id    = _talkId(t);
  const href  = _talkHref(t);
  const short = CONF_SHORT[t.conf] || t.conf;
  const color = CONF_COLOR[t.conf] || '#999';
  const ts    = String(Math.floor(t.start_min/60)).padStart(2,'0') + ':' + String(t.start_min%60).padStart(2,'0');
  const tl    = t.end_str ? ts + '\\u2013' + t.end_str + ' CEST' : ts;
  return `data-title="${he(t.title)}" data-paper="${he(t.paper)}" data-author="${he(t.author)}" ` +
         `data-url="${he(href)}" data-conf="${he(t.conf)}" data-short="${he(short)}" ` +
         `data-color="${he(color)}" data-time="${he(tl)}" data-room="${he(t.room)}" data-day-label="${he(dayLabel)}"`;
}

function _timeBounds(t) {
  const s = t.start_min;
  if (t.end_str) {
    const p = t.end_str.split(':');
    const e = parseInt(p[0]) * 60 + parseInt(p[1]);
    if (!isNaN(e)) return [s, e];
  }
  return [s, s + 20];
}

// ── Calendar card ──────────────────────────────────────────────────────────
function _renderCalCard(t, top, height, dayLabel) {
  const id      = _talkId(t);
  const color   = CONF_COLOR[t.conf] || '#999';
  const short   = CONF_SHORT[t.conf] || t.conf;
  const search  = he(t.title + ' ' + t.paper + ' ' + t.author);
  const plenary = t.conf === 'PLENARY';
  const cardSt  = plenary
    ? `background:#1a1a2e;border-left-color:#fff;top:${top}px;height:${height}px`
    : `border-left-color:${color};top:${top}px;height:${height}px`;
  const confSt  = plenary ? 'color:#fff' : `color:${color}`;
  const titlSt  = plenary ? 'color:#fff' : '';
  const meta    = t.conf !== 'PLENARY'
    ? `<div class="talk-meta">[${he(t.paper)}] ${he(t.author)}</div>` : '';
  return `<div class="talk cal-talk" data-search="${search}" data-id="${he(id)}" ${_modalAttrs(t, dayLabel)} style="${cardSt}">` +
    `<div class="talk-header"><span class="talk-conf" style="${confSt}">${he(short)}</span>` +
    `<button class="star-btn" onclick="toggleBookmark(this)" title="Save to My Schedule">☆</button></div>` +
    `<div class="talk-title" style="${titlSt}"><span class="talk-link" onclick="openTalkModal(this)">${he(t.title)}</span></div>` +
    meta + `</div>`;
}

// ── Session item (inside concurrent-talks block) ───────────────────────────
function _renderSessionItem(t, dayLabel) {
  const id     = _talkId(t);
  const color  = CONF_COLOR[t.conf] || '#999';
  const short  = CONF_SHORT[t.conf] || t.conf;
  const search = he(t.title + ' ' + t.paper + ' ' + t.author);
  const meta   = t.conf !== 'PLENARY'
    ? `<div class="talk-meta">[${he(t.paper)}] ${he(t.author)}</div>` : '';
  return `<div class="talk session-item" data-search="${search}" data-id="${he(id)}" ${_modalAttrs(t, dayLabel)} style="border-left-color:${color}">` +
    `<div class="talk-header"><span class="talk-conf" style="color:${color}">${he(short)}</span>` +
    `<button class="star-btn" onclick="toggleBookmark(this)" title="Save to My Schedule">☆</button></div>` +
    `<div class="talk-title"><span class="talk-link" onclick="openTalkModal(this)">${he(t.title)}</span></div>` +
    meta + `</div>`;
}

// ── Session block (group of concurrent talks) ──────────────────────────────
function _renderSessionBlock(talks, top, height, ts, te, dayLabel) {
  const fmt = m => String(Math.floor(m/60)).padStart(2,'0') + ':' + String(m%60).padStart(2,'0');
  const label = `${fmt(ts)}\\u2013${fmt(te)} CEST`;
  return `<div class="cal-session" style="top:${top}px;height:${height}px">` +
    `<div class="session-header"><span>${label}</span><span>${talks.length} talks</span></div>` +
    `<div class="session-list">${talks.map(t => _renderSessionItem(t, dayLabel)).join('')}</div></div>`;
}

// ── Full calendar grid for one day ─────────────────────────────────────────
function _renderCalendarDay(day) {
  const { day_start_min: ds, day_end_min: de, rooms, rooms_map } = day;
  const total_min = de - ds;
  const PX = 4, COL_W = 180;
  const PST = 17*60+30, PET = 19*60;

  let marks = '', lines = '';
  for (let off = 0; off <= total_min; off += 30) {
    const top = off * PX;
    const am  = ds + off;
    const lbl = String(Math.floor(am/60)).padStart(2,'0') + ':' + String(am%60).padStart(2,'0');
    marks += `<div class="cal-mark${off===0?' first-mark':''}" style="top:${top}px">${lbl}</div>`;
    lines += `<div class="${am%60===0?'cal-hour-line':'cal-half-line'}" style="top:${top}px"></div>`;
  }
  if (PST >= ds && PST < de) {
    const pt = (PST-ds)*PX, ph = (Math.min(PET,de)-PST)*PX;
    lines += `<div class="cal-poster-band" style="top:${pt}px;height:${ph}px"></div>`;
  }

  let cols = '';
  for (const room of rooms) {
    const sorted = [...(rooms_map[room]||[])].sort((a,b) => {
      const [as] = _timeBounds(a); const [bs] = _timeBounds(b); return as-bs;
    });
    // group by identical time bounds
    const groups = []; const gmap = new Map();
    for (const t of sorted) {
      const [s,e] = _timeBounds(t); const k = `${s}-${e}`;
      if (!gmap.has(k)) { gmap.set(k, groups.length); groups.push({s,e,talks:[]}); }
      groups[gmap.get(k)].talks.push(t);
    }
    let cards = '';
    for (const {s:ts, e:te, talks:grp} of groups) {
      const top = (ts-ds)*PX, h = Math.max(te-ts,5)*PX;
      cards += grp.length===1 ? _renderCalCard(grp[0],top,h,day.label) : _renderSessionBlock(grp,top,h,ts,te,day.label);
    }
    cols += `<div class="cal-col">${cards}</div>`;
  }

  const tw = rooms.length * COL_W;
  const rh = rooms.map(r=>`<div class="cal-room-head">${he(r)}</div>`).join('');
  const tp = total_min * PX;
  return `<div class="cal-wrap">` +
    `<div class="cal-header-row"><div class="cal-gutter-ph"></div>${rh}</div>` +
    `<div class="cal-body">` +
    `<div class="cal-gutter" style="height:${tp}px">${marks}</div>` +
    `<div class="cal-timeline" style="height:${tp}px;width:${tw}px">${lines}<div class="cal-cols">${cols}</div></div>` +
    `</div></div>`;
}

// ── Agenda (mobile flat list) for one day ──────────────────────────────────
function _renderAgendaDay(day) {
  const talks = [];
  for (const rm of day.rooms) for (const t of (day.rooms_map[rm]||[])) talks.push(t);
  talks.sort((a,b) => a.start_min-b.start_min || a.room.localeCompare(b.room) || a.title.localeCompare(b.title));
  let rows = '', lastHour = -1;
  for (const t of talks) {
    const h = Math.floor(t.start_min/60);
    if (h !== lastHour) {
      lastHour = h;
      rows += `<div class="agenda-hour-sep" style="top:var(--tabs-h,0)"><span>${String(h).padStart(2,'0')}:00</span></div>`;
    }
    const id      = _talkId(t);
    const color   = CONF_COLOR[t.conf] || '#999';
    const short   = CONF_SHORT[t.conf] || t.conf;
    const search  = he(t.title + ' ' + t.paper + ' ' + t.author);
    const plenary = t.conf === 'PLENARY';
    const ts      = String(Math.floor(t.start_min/60)).padStart(2,'0') + ':' + String(t.start_min%60).padStart(2,'0');
    const endH    = t.end_str ? `<span class="agenda-time-end">${he(t.end_str)}</span>` : '';
    const meta    = [t.room, t.author].filter(p=>p&&p!=='Room TBC').map(p=>he(p)).join(' · ');
    rows += `<div class="agenda-row talk${plenary?' agenda-row--plenary':''}" data-search="${search}" data-id="${he(id)}" ${_modalAttrs(t, day.label)} style="border-left-color:${color}">` +
      `<div class="agenda-time-col"><span class="agenda-time-start">${ts}</span>${endH}</div>` +
      `<div class="agenda-event-col"><span class="agenda-conf" style="color:${color}">${he(short)}</span>` +
      `<div class="agenda-title"><span class="talk-link" onclick="openTalkModal(this)">${he(t.title)}</span></div>` +
      (meta ? `<div class="agenda-meta">${meta}</div>` : '') + `</div>` +
      `<button class="star-btn" onclick="toggleBookmark(this)" title="Save to My Schedule"${plenary?' style="color:#7eb8f7"':''}>&#9734;</button>` +
      `</div>`;
  }
  return `<div class="cal-agenda">${rows}</div>`;
}

// ── Build one schedule day on demand ───────────────────────────────────────
function _buildScheduleDay(day) {
  if (_builtScheduleDays.has(day.date_iso)) return;
  _builtScheduleDays.add(day.date_iso);
  const panel = document.getElementById('day-' + day.date_iso);
  if (!panel) return;
  panel.innerHTML = _renderCalendarDay(day) + _renderAgendaDay(day);
  _applyState(panel);
}

// ── Talk list ──────────────────────────────────────────────────────────────
function _renderTalkListItem(t, date_iso, dayLabel) {
  const id    = _talkId(t);
  const color = CONF_COLOR[t.conf] || '#999';
  const short = CONF_SHORT[t.conf] || t.conf;
  const search = he(t.title + ' ' + t.paper + ' ' + t.author);
  const ts    = String(Math.floor(t.start_min/60)).padStart(2,'0') + ':' + String(t.start_min%60).padStart(2,'0');
  const tl    = t.end_str ? ts + '\\u2013' + t.end_str : ts;
  const meta  = t.conf !== 'PLENARY' ? `[${he(t.paper)}] ${he(t.author)}` : '';
  return `<div class="talk-list-item" data-search="${search}" data-id="${he(id)}" ` +
    `data-day="${he(date_iso)}" data-day-label="${he(dayLabel)}" ${_modalAttrs(t)}>` +
    `<div class="talk-list-time">${tl}<br>${he(t.room)}</div>` +
    `<div class="talk-list-body"><span class="talk-list-conf" style="color:${color}">${he(short)}</span>` +
    `<div class="talk-list-title"><span class="talk-link" onclick="openTalkModal(this)">${he(t.title)}</span></div>` +
    (meta ? `<div class="talk-list-meta">${meta}</div>` : '') + `</div>` +
    `<button class="talk-skip-btn" onclick="toggleTalkSkip(this)" title="Not interested">&#10005;</button>` +
    `<button class="star-btn" onclick="toggleBookmark(this)" title="Save to My Schedule">&#9734;</button>` +
    `</div>`;
}

function _ensureTalkListBuilt() {
  if (_talkListBuilt) return;
  _talkListBuilt = true;
  const body = document.getElementById('talklist-body');
  if (!body) return;
  let tabs = `<button class="tab-btn active" data-day="all" onclick="switchTalkListDay('all')" style="font-size:12px;padding:5px 14px">All days</button>`;
  let panels = '<span id="talklist-star-count"></span>';
  for (const day of ALL_DAYS) {
    tabs += `<button class="tab-btn" data-day="${day.date_iso}" onclick="switchTalkListDay('${day.date_iso}')" style="font-size:12px;padding:5px 14px">${he(day.label)}</button>`;
    const talks = [];
    for (const rm of day.rooms) for (const t of (day.rooms_map[rm]||[])) talks.push(t);
    talks.sort((a,b) => a.start_min-b.start_min || a.room.localeCompare(b.room) || a.title.localeCompare(b.title));
    panels += `<div class="talk-list-day-panel active" id="talklist-day-${day.date_iso}">` +
      talks.map(t => _renderTalkListItem(t, day.date_iso, day.label)).join('') + `</div>`;
  }
  body.innerHTML = `<div class="tabs">${tabs}</div>` + panels;
  _applyState(body);
  updateTalkListCount();
}

// ── Poster list ────────────────────────────────────────────────────────────
function _renderPosterItem(t, conf, date_iso, dayLabel) {
  const id    = he(t.paper);
  const color = CONF_COLOR[conf] || '#999';
  const short = CONF_SHORT[conf] || conf;
  const search = he(t.title + ' ' + t.paper + ' ' + t.author);
  const tc    = {...t, conf};
  return `<div class="poster-item" data-id="${id}" data-search="${search}" ` +
    `data-day="${he(date_iso)}" data-day-label="${he(dayLabel)}" ${_modalAttrs(tc)}>` +
    `<div class="poster-item-body">` +
    `<div class="poster-item-title"><span class="talk-link" onclick="openTalkModal(this)">${he(t.title)}</span></div>` +
    `<div class="poster-item-meta"><span class="poster-item-conf" style="color:${color}">${he(short)}</span>` +
    ` &middot; [${id}] ${he(t.author)}</div></div>` +
    `<div class="poster-actions">` +
    `<button class="poster-skip-btn" onclick="togglePosterSkip(this)" title="Not interested">&#10005;</button>` +
    `<button class="poster-star-btn" onclick="togglePosterBookmark(this)" title="Save to My Schedule">&#9734;</button>` +
    `</div></div>`;
}

function _ensurePosterBuilt() {
  if (_posterBuilt) return;
  _posterBuilt = true;
  const body = document.getElementById('poster-body');
  if (!body) return;
  let tabs = `<button class="tab-btn active" data-day="all" onclick="switchPosterDay('all')" style="font-size:12px;padding:5px 14px">All days</button>`;
  let panels = '<span id="poster-star-count"></span>';
  for (const day of ALL_POSTER_DAYS) {
    tabs += `<button class="tab-btn" data-day="${day.date_iso}" onclick="switchPosterDay('${day.date_iso}')" style="font-size:12px;padding:5px 14px">${he(day.label)}</button>`;
    let items = '';
    for (const [conf, talks] of Object.entries(day.confs_map))
      for (const t of talks) items += _renderPosterItem(t, conf, day.date_iso, day.label);
    panels += `<div class="poster-day-panel active" id="poster-day-${day.date_iso}">${items}</div>`;
  }
  body.innerHTML = `<div class="tabs">${tabs}</div>` + panels;
  _applyState(body);
  applyPosterSearch();
}

// ── Apply bookmarks/skipped/filters to a freshly-built container ───────────
function _applyState(el) {
  el.querySelectorAll('.talk, .talk-list-item').forEach(c => {
    const on = bookmarks.has(c.dataset.id);
    c.classList.toggle('bookmarked', on);
    const star = c.querySelector('.star-btn');
    if (star) star.textContent = on ? '\\u2605' : '\\u2606';
  });
  el.querySelectorAll('.talk-list-item').forEach(c => {
    const on = skipped.has(c.dataset.id);
    c.classList.toggle('skipped', on);
    const btn = c.querySelector('.talk-skip-btn');
    if (btn) btn.innerHTML = on ? UNDO_ICON : '&#10005;';
  });
  el.querySelectorAll('.poster-item').forEach(c => {
    const id = c.dataset.id;
    const bk = bookmarks.has(id), sk = skipped.has(id);
    c.classList.toggle('bookmarked', bk);
    c.classList.toggle('skipped', sk);
    const star = c.querySelector('.poster-star-btn');
    if (star) star.textContent = bk ? '\\u2605' : '\\u2606';
    const skip = c.querySelector('.poster-skip-btn');
    if (skip) skip.innerHTML = sk ? UNDO_ICON : '&#10005;';
  });
  if (confFilters.size > 0)
    el.querySelectorAll('.talk,.talk-list-item,.poster-item').forEach(c =>
      c.classList.toggle('conf-hidden', !confFilters.has(c.dataset.conf)));
}

// ── Schedule initialisation (runs after all JS is defined) ─────────────────
(function initSchedule() {
  const body   = document.getElementById('schedule-body');
  const tabsEl = document.getElementById('schedule-tabs');
  if (!body || !tabsEl || !ALL_DAYS.length) return;
  ALL_DAYS.forEach((day, i) => {
    const btn = document.createElement('button');
    btn.className = 'tab-btn' + (i === 0 ? ' active' : '');
    btn.dataset.day = day.date_iso;
    btn.textContent = day.label;
    btn.onclick = () => switchDay(day.date_iso);
    tabsEl.appendChild(btn);
    const panel = document.createElement('div');
    panel.className = 'day-panel';
    panel.id = 'day-' + day.date_iso;
    panel.style.display = i === 0 ? 'block' : 'none';
    body.appendChild(panel);
  });
  _buildScheduleDay(ALL_DAYS[0]);
  updateStickyOffset();
})();
"""

JS = """
const UNDO_ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18" style="display:block"><path fill-rule="evenodd" d="M9.53 2.47a.75.75 0 0 1 0 1.06L4.81 8.25H15a6.75 6.75 0 0 1 0 13.5h-3a.75.75 0 0 1 0-1.5h3a5.25 5.25 0 1 0 0-10.5H4.81l4.72 4.72a.75.75 0 1 1-1.06 1.06l-6-6a.75.75 0 0 1 0-1.06l6-6a.75.75 0 0 1 1.06 0Z" clip-rule="evenodd"/></svg>`;

const LS_KEY = 'spie_as26_bookmarks';
let bookmarks = new Set(JSON.parse(localStorage.getItem(LS_KEY) || '[]'));
let myScheduleActive = false;
let confFilters = new Set();

function toggleConfFilter(conf) {
  if (confFilters.has(conf)) {
    confFilters.delete(conf);
  } else {
    confFilters.add(conf);
  }
  document.querySelectorAll('.legend-item[data-conf]').forEach(item => {
    item.classList.toggle('inactive',
      confFilters.size > 0 && !confFilters.has(item.dataset.conf));
  });
  document.getElementById('clear-conf-btn').style.display = confFilters.size > 0 ? '' : 'none';
  applyConfFilter();
  applySearch();
}

function clearConfFilters() {
  confFilters.clear();
  document.querySelectorAll('.legend-item[data-conf]').forEach(item => item.classList.remove('inactive'));
  document.getElementById('clear-conf-btn').style.display = 'none';
  applyConfFilter();
  applySearch();
}

function applyConfFilter() {
  document.querySelectorAll('.talk, .talk-list-item, .poster-item').forEach(el => {
    el.classList.toggle('conf-hidden',
      confFilters.size > 0 && !confFilters.has(el.dataset.conf));
  });
}

function saveBookmarks(sync = true) {
  localStorage.setItem(LS_KEY, JSON.stringify([...bookmarks]));
  updateBookmarkCount();
  updateTalkListCount();
  if (sync) schedulePush();
}

function updateTalkListCount() {
  const countEl = document.getElementById('talklist-star-count');
  if (!countEl) return;
  let starred = 0, total = 0;
  document.querySelectorAll('.talk-list-day-panel.active').forEach(panel => {
    panel.querySelectorAll('.talk-list-item').forEach(t => {
      if (!t.classList.contains('conf-hidden')) {
        total++;
        if (t.classList.contains('bookmarked')) starred++;
      }
    });
  });
  countEl.textContent = starred ? starred + ' ★ / ' + total + ' talks' : total + ' talks';
}

function updateBookmarkCount() {
  const n = bookmarks.size;
  document.getElementById('bookmark-count').textContent =
    n ? n + ' saved' : '';
}

function toggleBookmark(btn) {
  const card = btn.closest('[data-id]');
  const id = card.dataset.id;
  const wasBookmarked = bookmarks.has(id);
  if (wasBookmarked) {
    bookmarks.delete(id);
  } else {
    bookmarks.add(id);
  }
  document.querySelectorAll('[data-id="' + CSS.escape(id) + '"]').forEach(el => {
    el.classList.toggle('bookmarked', !wasBookmarked);
    const star = el.querySelector('.star-btn');
    if (star) star.textContent = wasBookmarked ? '☆' : '★';
  });
  saveBookmarks();
}

function restoreBookmarks() {
  document.querySelectorAll('.talk, .talk-list-item').forEach(card => {
    const on = bookmarks.has(card.dataset.id);
    card.classList.toggle('bookmarked', on);
    card.querySelector('.star-btn').textContent = on ? '★' : '☆';
  });
}

function toggleMySchedule() {
  myScheduleActive = !myScheduleActive;
  document.body.classList.toggle('my-schedule-mode', myScheduleActive);
  const btn = document.getElementById('my-schedule-btn');
  btn.classList.toggle('active', myScheduleActive);
  if (myScheduleActive) {
    document.getElementById('search').value = '';
    document.querySelectorAll('.talk').forEach(t => t.classList.remove('dim', 'match'));
    document.getElementById('match-count').textContent = '';
  }
  applyConfFilter();
  applySearch();
  applyPosterSearch();
}

function switchDay(iso) {
  const day = ALL_DAYS.find(d => d.date_iso === iso);
  if (day) _buildScheduleDay(day);
  document.querySelectorAll('.day-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('#schedule-body .tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('day-' + iso).style.display = 'block';
  document.querySelector('#schedule-body [data-day="' + iso + '"]').classList.add('active');
  applySearch();
}

function applySearch() {
  const q = document.getElementById('search').value.toLowerCase().trim();
  let n = 0;

  if (document.getElementById('page-talklist').classList.contains('active')) {
    document.querySelectorAll('.talk-list-day-panel.active').forEach(panel => {
      panel.querySelectorAll('.talk-list-item').forEach(t => {
        const searchOk = !q || t.dataset.search.toLowerCase().includes(q) ||
          (TALK_DATA[t.dataset.id]?.abstract || '').toLowerCase().includes(q);
        const scheduleOk = !myScheduleActive || t.classList.contains('bookmarked');
        const visible = searchOk && scheduleOk;
        t.style.display = visible ? '' : 'none';
        if (visible && q && !t.classList.contains('conf-hidden')) n++;
      });
      const anyVisible = [...panel.querySelectorAll('.talk-list-item')].some(
        t => t.style.display !== 'none' && !t.classList.contains('conf-hidden'));
      panel.style.display = anyVisible ? '' : 'none';
    });
    document.getElementById('match-count').textContent =
      q ? n + ' match' + (n !== 1 ? 'es' : '') : '';
    updateTalkListCount();
    return;
  }

  if (document.getElementById('page-posters').classList.contains('active')) {
    applyPosterSearch();
    return;
  }

  // Schedule view
  const panel = document.querySelector('.day-panel[style*="block"]');
  if (!panel) return;
  panel.querySelectorAll('.talk').forEach(t => {
    if (t.classList.contains('conf-hidden')) { t.classList.remove('dim', 'match'); return; }
    const text = t.dataset.search.toLowerCase();
    const abstract = (TALK_DATA[t.dataset.id]?.abstract || '').toLowerCase();
    if (!q) {
      t.classList.remove('dim', 'match');
    } else if (text.includes(q) || abstract.includes(q)) {
      t.classList.remove('dim');
      t.classList.add('match');
      n++;
    } else {
      t.classList.add('dim');
      t.classList.remove('match');
    }
  });
  document.getElementById('match-count').textContent =
    q ? n + ' match' + (n !== 1 ? 'es' : '') : '';
}

function clearSearch() {
  document.getElementById('search').value = '';
  applySearch();
}

document.getElementById('search').addEventListener('input', () => {
  if (myScheduleActive) toggleMySchedule();
  applySearch();
});
document.getElementById('search').addEventListener('keydown', ev => {
  if (ev.key === 'Escape') clearSearch();
});

function updateStickyOffset() {
  const topbarH = document.querySelector('.topbar').offsetHeight;
  const legendH = document.querySelector('.legend').offsetHeight;
  const viewNavH = document.querySelector('.view-nav').offsetHeight;
  const totalH = topbarH + legendH + viewNavH;
  document.documentElement.style.setProperty('--topbar-h', topbarH + 'px');
  const tabsEl = document.querySelector('#schedule-body .tabs');
  if (tabsEl) {
    document.documentElement.style.setProperty('--tabs-h', tabsEl.offsetHeight + 'px');
  }
  const posterTabsEl = document.querySelector('#poster-body .tabs');
  if (posterTabsEl) {
    document.documentElement.style.setProperty('--poster-tabs-h', posterTabsEl.offsetHeight + 'px');
  }
  const contentH = window.innerHeight - totalH;
  ['schedule-body', 'poster-body', 'talklist-body', 'swipe-body', 'talkswipe-body'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.height = contentH + 'px';
  });
}
updateStickyOffset();
window.addEventListener('resize', updateStickyOffset);

restoreBookmarks();
updateBookmarkCount();

// ── Export / Import ──
function openShareModal() {
  updateSyncCodeDisplay();
  document.getElementById('sync-notice').textContent = '';
  document.getElementById('link-code-input').value = '';
  const data = { bookmarks: [...bookmarks], skipped: [...skipped] };
  document.getElementById('export-code').value = JSON.stringify(data, null, 2);
  document.getElementById('import-code').value = '';
  document.getElementById('share-notice').textContent = '';
  document.getElementById('share-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeShareModal() {
  document.getElementById('share-modal').classList.remove('open');
  document.body.style.overflow = '';
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
    const parsed = JSON.parse(raw);
    let bIds, sIds;
    if (Array.isArray(parsed)) {
      bIds = parsed; sIds = [];
    } else {
      bIds = parsed.bookmarks || [];
      sIds = parsed.skipped || [];
    }
    bookmarks = new Set(bIds);
    skipped = new Set(sIds);
    saveBookmarks();
    saveSkipped();
    restoreBookmarks();
    restorePosterStates();
    restoreTalkListSkipped();
    const msg = bIds.length + ' bookmark' + (bIds.length !== 1 ? 's' : '') +
      (sIds.length ? ', ' + sIds.length + ' skipped' : '') + ' imported.';
    document.getElementById('share-notice').textContent = msg;
  } catch {
    document.getElementById('share-notice').textContent = 'Invalid code — please try again.';
  }
}

function clearAllBookmarks() {
  if (!confirm('Remove all saved and skipped talks?')) return;
  bookmarks = new Set();
  skipped = new Set();
  saveBookmarks();
  saveSkipped();
  document.querySelectorAll('.talk.bookmarked, .talk-list-item.bookmarked').forEach(c => {
    c.classList.remove('bookmarked');
    const star = c.querySelector('.star-btn');
    if (star) star.textContent = '☆';
  });
  document.querySelectorAll('.talk-list-item.skipped').forEach(c => {
    c.classList.remove('skipped');
    const btn = c.querySelector('.talk-skip-btn');
    if (btn) btn.textContent = '✕';
  });
  document.querySelectorAll('.poster-item.bookmarked, .poster-item.skipped').forEach(c => {
    c.classList.remove('bookmarked', 'skipped');
    const star = c.querySelector('.poster-star-btn');
    if (star) star.textContent = '☆';
    const skip = c.querySelector('.poster-skip-btn');
    if (skip) skip.textContent = '✕';
  });
  document.getElementById('export-code').value = '';
  document.getElementById('share-notice').textContent = 'All bookmarks and skipped cleared.';
}

document.getElementById('share-modal').addEventListener('click', ev => {
  if (ev.target === ev.currentTarget) closeShareModal();
});

// ── View switcher ──
function toggleViewMenu() {
  document.querySelector('.view-nav').classList.toggle('open');
}
document.addEventListener('click', ev => {
  const nav = document.querySelector('.view-nav');
  if (nav.classList.contains('open') && !nav.contains(ev.target)) nav.classList.remove('open');
});

function switchView(view) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + view).classList.add('active');
  document.querySelector('[data-view="' + view + '"]').classList.add('active');
  const label = document.getElementById('view-current-label');
  if (label) label.textContent = document.querySelector('.view-btn[data-view="' + view + '"]').textContent.trim();
  document.querySelector('.view-nav').classList.remove('open');
  updateStickyOffset();
  if (view === 'talklist') _ensureTalkListBuilt();
  if (view === 'posters')  _ensurePosterBuilt();
  if (view === 'swipe')    { _ensurePosterBuilt(); initSwipe(); }
  if (view === 'talkswipe') { _ensureTalkListBuilt(); initTalkSwipe(); }
  const isSwipe = view === 'swipe' || view === 'talkswipe';
  const sw = document.querySelector('.search-wrap');
  sw.style.opacity = isSwipe ? '0.35' : '';
  sw.style.pointerEvents = isSwipe ? 'none' : '';
  const placeholders = {
    schedule:   'Search talks: title, author, abstract…',
    talklist:   'Search talks: title, author, abstract…',
    talkswipe:  '',
    posters:    'Search posters: title, author, abstract…',
    swipe:      '',
  };
  document.getElementById('search').placeholder = placeholders[view] || 'Search…';
  document.getElementById('match-count').textContent = '';
  applySearch();
}

function switchTalkListDay(iso) {
  if (iso === 'all') {
    document.querySelectorAll('.talk-list-day-panel').forEach(p => p.classList.add('active'));
  } else {
    document.querySelectorAll('.talk-list-day-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('talklist-day-' + iso).classList.add('active');
  }
  document.querySelectorAll('#talklist-body .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('#talklist-body [data-day="' + iso + '"]').classList.add('active');
  applySearch();
  updateTalkListCount();
}

// ── Poster page ──
const LS_SKIP = 'spie_as26_skipped';
let skipped = new Set(JSON.parse(localStorage.getItem(LS_SKIP) || '[]'));

function saveSkipped(sync = true) {
  localStorage.setItem(LS_SKIP, JSON.stringify([...skipped]));
  if (sync) schedulePush();
}

function togglePosterBookmark(btn) {
  const item = btn.closest('.poster-item');
  const id = item.dataset.id;
  if (bookmarks.has(id)) {
    bookmarks.delete(id);
    item.classList.remove('bookmarked');
    btn.textContent = '☆';
  } else {
    bookmarks.add(id);
    item.classList.add('bookmarked');
    btn.textContent = '★';
    // un-skip if previously skipped
    if (skipped.has(id)) {
      skipped.delete(id);
      saveSkipped();
      item.classList.remove('skipped');
      item.querySelector('.poster-skip-btn').textContent = '✕';
    }
  }
  saveBookmarks();
  applyPosterSearch();
}

function togglePosterSkip(btn) {
  const item = btn.closest('.poster-item');
  const id = item.dataset.id;
  if (skipped.has(id)) {
    skipped.delete(id);
    item.classList.remove('skipped');
    btn.textContent = '✕';
  } else {
    skipped.add(id);
    item.classList.add('skipped');
    btn.innerHTML = UNDO_ICON;
    // un-bookmark if previously bookmarked
    if (bookmarks.has(id)) {
      bookmarks.delete(id);
      item.classList.remove('bookmarked');
      item.querySelector('.poster-star-btn').textContent = '☆';
      saveBookmarks();
    }
  }
  saveSkipped();
}

function switchPosterDay(iso) {
  if (iso === 'all') {
    document.querySelectorAll('.poster-day-panel').forEach(p => p.classList.add('active'));
  } else {
    document.querySelectorAll('.poster-day-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('poster-day-' + iso).classList.add('active');
  }
  document.querySelectorAll('#poster-body .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('#poster-body [data-day="' + iso + '"]').classList.add('active');
  applyPosterSearch();
}

function applyPosterSearch() {
  const q = document.getElementById('search').value.toLowerCase().trim();
  const panels = document.querySelectorAll('.poster-day-panel.active');
  if (!panels.length) return;
  let matchCount = 0, total = 0, starred = 0;
  panels.forEach(panel => {
    panel.querySelectorAll('.poster-item').forEach(item => {
      const text = item.dataset.search.toLowerCase();
      const abstract = (TALK_DATA[item.dataset.id]?.abstract || '').toLowerCase();
      const searchOk = !q || text.includes(q) || abstract.includes(q);
      const scheduleOk = !myScheduleActive || item.classList.contains('bookmarked');
      if (searchOk && scheduleOk) {
        item.style.display = '';
        if (q && !item.classList.contains('conf-hidden')) matchCount++;
      } else {
        item.style.display = 'none';
      }
      if (!item.classList.contains('conf-hidden')) total++;
      if (item.classList.contains('bookmarked') && !item.classList.contains('conf-hidden')) starred++;
    });
    const anyVisible = [...panel.querySelectorAll('.poster-item')].some(
      item => item.style.display !== 'none' && !item.classList.contains('conf-hidden'));
    panel.style.display = anyVisible ? '' : 'none';
  });
  document.getElementById('match-count').textContent =
    q ? matchCount + ' match' + (matchCount !== 1 ? 'es' : '') : '';
  const countEl = document.getElementById('poster-star-count');
  if (countEl) countEl.textContent = starred ? starred + ' ★ / ' + total : total + ' posters';
}

function toggleTalkSkip(btn) {
  const item = btn.closest('.talk-list-item');
  const id = item.dataset.id;
  if (skipped.has(id)) {
    skipped.delete(id);
    item.classList.remove('skipped');
    btn.textContent = '✕';
  } else {
    skipped.add(id);
    item.classList.add('skipped');
    btn.innerHTML = UNDO_ICON;
    if (bookmarks.has(id)) {
      bookmarks.delete(id);
      item.classList.remove('bookmarked');
      const star = item.querySelector('.star-btn');
      if (star) star.textContent = '☆';
      saveBookmarks();
    }
  }
  saveSkipped();
}

function restoreTalkListSkipped() {
  document.querySelectorAll('.talk-list-item').forEach(item => {
    const on = skipped.has(item.dataset.id);
    item.classList.toggle('skipped', on);
    const btn = item.querySelector('.talk-skip-btn');
    if (btn) btn.innerHTML = on ? UNDO_ICON : '&#10005;';
  });
}
restoreTalkListSkipped();

function restorePosterStates() {
  document.querySelectorAll('.poster-item').forEach(item => {
    const id = item.dataset.id;
    const starred = bookmarks.has(id);
    const skip    = skipped.has(id);
    item.classList.toggle('bookmarked', starred);
    item.querySelector('.poster-star-btn').textContent = starred ? '★' : '☆';
    item.classList.toggle('skipped', skip);
    item.querySelector('.poster-skip-btn').innerHTML = skip ? UNDO_ICON : '&#10005;';
  });
}
restorePosterStates();

// ── Swipe game ──
let swipeQueue = [];
let swipeIdx = 0;
let swipeHistory = [];
let swipeInitialized = false;
let swipeFilterDay = 'all';
let swipeFilterConf = 'all';

function buildSwipeQueue() {
  _ensurePosterBuilt();
  const seen = new Set();
  swipeQueue = Array.from(document.querySelectorAll('.poster-item'))
    .filter(el => {
      if (seen.has(el.dataset.id)) return false;
      seen.add(el.dataset.id);
      if (swipeFilterDay !== 'all' && el.dataset.day !== swipeFilterDay) return false;
      if (swipeFilterConf !== 'all' && el.dataset.conf !== swipeFilterConf) return false;
      return !bookmarks.has(el.dataset.id) && !skipped.has(el.dataset.id);
    })
    .map(el => ({
      id: el.dataset.id,
      conf: el.dataset.conf,
      day: el.dataset.day,
      dayLabel: el.dataset.dayLabel || '',
      title: el.dataset.title,
      paper: el.dataset.paper,
      author: el.dataset.author,
      abstract: TALK_DATA[el.dataset.id]?.abstract || '',
      url: el.dataset.url,
      color: el.dataset.color,
      short: el.dataset.short,
    }));
  swipeIdx = 0;
  swipeHistory = [];
}

function swipeEscape(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderSwipeCard(talk, stackPos) {
  const offset = stackPos * 4;
  const scale = 1 - stackPos * 0.04;
  const style = `transform: translateY(${offset}px) scale(${scale}); z-index: ${10 - stackPos};`;
  const href = talk.url ? `https://spie.org${talk.url}` : '';
  const metaParts = [talk.paper, talk.author].filter(Boolean);
  const dayMeta = swipeFilterDay === 'all' && talk.dayLabel ? `<div class="swipe-card-meta" style="font-size:10px;opacity:.7">${swipeEscape(talk.dayLabel)}</div>` : '';
  return `<div class="swipe-card" data-id="${swipeEscape(talk.id)}"
  data-title="${swipeEscape(talk.title)}" data-paper="${swipeEscape(talk.paper)}"
  data-author="${swipeEscape(talk.author)}" data-abstract="${swipeEscape(talk.abstract || '')}"
  data-url="${swipeEscape(href)}" data-short="${swipeEscape(talk.short)}" data-color="${swipeEscape(talk.color)}"
  style="${style}">
  <div class="swipe-hint-skip">SKIP</div>
  <div class="swipe-hint-save">SAVE ★</div>
  <div class="swipe-card-conf" style="color:${talk.color}">${swipeEscape(talk.short)}</div>
  <div class="swipe-card-title"><span class="talk-link" onclick="openTalkModal(this)">${swipeEscape(talk.title)}</span></div>
  ${ metaParts.length ? `<div class="swipe-card-meta">${swipeEscape(metaParts.join(' · '))}</div>` : '' }
  ${dayMeta}
  ${ talk.abstract ? `<div class="swipe-card-abstract">${swipeEscape(talk.abstract)}</div>` : '' }
</div>`;
}

function updateSwipeArena() {
  const arena = document.getElementById('swipe-arena');
  const counter = document.getElementById('swipe-counter');
  arena.innerHTML = '';
  const remaining = swipeQueue.length - swipeIdx;
  counter.textContent = remaining + ' remaining';
  if (remaining === 0) {
    arena.innerHTML = '<div class="swipe-done"><strong>All done!</strong><br>Every poster in this filter has been reviewed.<br>Use the filters above or Reset to start again.</div>';
    return;
  }
  // render up to 3 cards (front to back — querySelector returns front card first)
  const preview = Math.min(3, remaining);
  for (let i = 0; i < preview; i++) {
    arena.innerHTML += renderSwipeCard(swipeQueue[swipeIdx + i], i);
  }
  attachDragToTop();
}

function applySwipeAction(action) {
  if (swipeIdx >= swipeQueue.length) return;
  const talk = swipeQueue[swipeIdx];
  const topCard = document.querySelector('#swipe-arena .swipe-card');
  swipeHistory.push({ talk, action });

  const flyClass = action === 'save' ? 'fly-right' : action === 'skip' ? 'fly-left' : 'fly-left';
  if (topCard) {
    topCard.classList.add(flyClass);
    setTimeout(() => { topCard.remove(); }, 380);
  }

  if (action === 'save') {
    bookmarks.add(talk.id);
    saveBookmarks();
    // sync poster page
    const pItem = document.querySelector(`.poster-item[data-id="${CSS.escape(talk.id)}"]`);
    if (pItem) {
      pItem.classList.add('bookmarked');
      pItem.querySelector('.poster-star-btn').textContent = '★';
    }
    // sync schedule page
    document.querySelectorAll(`.talk[data-id="${CSS.escape(talk.id)}"]`).forEach(c => {
      c.classList.add('bookmarked');
      c.querySelector('.star-btn').textContent = '★';
    });
  } else {
    skipped.add(talk.id);
    saveSkipped();
    const pItem = document.querySelector(`.poster-item[data-id="${CSS.escape(talk.id)}"]`);
    if (pItem) {
      pItem.classList.add('skipped');
      pItem.querySelector('.poster-skip-btn').innerHTML = UNDO_ICON;
    }
  }

  swipeIdx++;
  // slight delay so fly animation plays
  setTimeout(updateSwipeArena, 80);
}

function undoSwipe() {
  if (!swipeHistory.length) return;
  const { talk, action } = swipeHistory.pop();
  if (action === 'save') {
    bookmarks.delete(talk.id);
    saveBookmarks();
    const pItem = document.querySelector(`.poster-item[data-id="${CSS.escape(talk.id)}"]`);
    if (pItem) { pItem.classList.remove('bookmarked'); pItem.querySelector('.poster-star-btn').textContent = '☆'; }
    document.querySelectorAll(`.talk[data-id="${CSS.escape(talk.id)}"]`).forEach(c => {
      c.classList.remove('bookmarked'); c.querySelector('.star-btn').textContent = '☆';
    });
  } else {
    skipped.delete(talk.id);
    saveSkipped();
    const pItem = document.querySelector(`.poster-item[data-id="${CSS.escape(talk.id)}"]`);
    if (pItem) { pItem.classList.remove('skipped'); pItem.querySelector('.poster-skip-btn').textContent = '✕'; }
  }
  swipeIdx--;
  updateSwipeArena();
}

function resetSwipe() {
  buildSwipeQueue();
  updateSwipeArena();
}

function initSwipe() {
  if (!swipeInitialized) {
    swipeInitialized = true;
    document.getElementById('swipe-filter-day').addEventListener('change', function() {
      swipeFilterDay = this.value;
      resetSwipe();
    });
    document.getElementById('swipe-filter-conf').addEventListener('change', function() {
      swipeFilterConf = this.value;
      resetSwipe();
    });
  }
  resetSwipe();
}

// Drag / touch on swipe card
function attachDragToTop() {
  const card = document.querySelector('#swipe-arena .swipe-card');
  if (!card) return;
  let startX = 0, startY = 0, curX = 0, curY = 0;

  function onStart(x, y) {
    startX = x; startY = y; curX = x; curY = y;
    card.classList.add('dragging');
  }
  function onMove(x, y) {
    if (!card.classList.contains('dragging')) return;
    curX = x; curY = y;
    const dx = curX - startX;
    const dy = curY - startY;
    const rot = dx * 0.08;
    card.style.transform = `translate(${dx}px, ${dy}px) rotate(${rot}deg)`;
    const skipHint = card.querySelector('.swipe-hint-skip');
    const saveHint = card.querySelector('.swipe-hint-save');
    skipHint.style.opacity = Math.max(0, Math.min(1, -dx / 80));
    saveHint.style.opacity = Math.max(0, Math.min(1, dx / 80));
  }
  function onEnd() {
    if (!card.classList.contains('dragging')) return;
    card.classList.remove('dragging');
    const dx = curX - startX;
    const dy = curY - startY;
    if (dx > 80) applySwipeAction('save');
    else if (dx < -80) applySwipeAction('skip');
    else {
      card.style.transform = '';
      card.querySelector('.swipe-hint-skip').style.opacity = 0;
      card.querySelector('.swipe-hint-save').style.opacity = 0;
    }
  }

  card.addEventListener('mousedown', ev => { ev.preventDefault(); onStart(ev.clientX, ev.clientY); });
  window.addEventListener('mousemove', ev => onMove(ev.clientX, ev.clientY));
  window.addEventListener('mouseup', () => onEnd());

  card.addEventListener('touchstart', ev => { const t = ev.touches[0]; onStart(t.clientX, t.clientY); }, { passive: true });
  card.addEventListener('touchmove', ev => {
    const t = ev.touches[0];
    if (card.classList.contains('dragging')) ev.preventDefault();
    onMove(t.clientX, t.clientY);
  }, { passive: false });
  card.addEventListener('touchend', () => onEnd());
}

document.addEventListener('keydown', ev => {
  if (!document.getElementById('page-swipe').classList.contains('active')) return;
  if (ev.key === 'ArrowRight' || ev.key === 'l') applySwipeAction('save');
  else if (ev.key === 'ArrowLeft' || ev.key === 'h') applySwipeAction('skip');
  else if (ev.key === 'ArrowUp' || ev.key === 'u') undoSwipe();
  else if (ev.key === 'ArrowDown' || ev.key === 'j') applySwipeAction('skip');
});

// ── Talk Swipe game ──
let talkSwipeQueue = [];
let talkSwipeIdx = 0;
let talkSwipeHistory = [];
let talkSwipeInitialized = false;
let talkSwipeFilterDay = 'all';
let talkSwipeFilterConf = 'all';

function buildTalkSwipeQueue() {
  _ensureTalkListBuilt();
  const seen = new Set();
  talkSwipeQueue = Array.from(document.querySelectorAll('.talk-list-item'))
    .filter(el => {
      if (seen.has(el.dataset.id)) return false;
      seen.add(el.dataset.id);
      if (talkSwipeFilterDay !== 'all' && el.dataset.day !== talkSwipeFilterDay) return false;
      if (talkSwipeFilterConf !== 'all' && el.dataset.conf !== talkSwipeFilterConf) return false;
      return !bookmarks.has(el.dataset.id) && !skipped.has(el.dataset.id);
    })
    .map(el => ({
      id: el.dataset.id,
      conf: el.dataset.conf,
      day: el.dataset.day,
      dayLabel: el.dataset.dayLabel || '',
      title: el.dataset.title,
      paper: el.dataset.paper,
      author: el.dataset.author,
      abstract: TALK_DATA[el.dataset.id]?.abstract || '',
      url: el.dataset.url,
      color: el.dataset.color,
      short: el.dataset.short,
      time: el.dataset.time || '',
      room: el.dataset.room || '',
    }));
  talkSwipeIdx = 0;
  talkSwipeHistory = [];
}

function renderTalkSwipeCard(talk, stackPos) {
  const offset = stackPos * 4;
  const scale = 1 - stackPos * 0.04;
  const style = `transform: translateY(${offset}px) scale(${scale}); z-index: ${10 - stackPos};`;
  const href = talk.url ? `https://spie.org${talk.url}` : '';
  const metaParts = [talk.paper, talk.author].filter(Boolean);
  const timeMeta = [talk.time, talk.room].filter(s => s && s !== 'Room TBC').join(' · ');
  const dayMeta = talkSwipeFilterDay === 'all' && talk.dayLabel ? talk.dayLabel : '';
  const locationLine = [dayMeta, timeMeta].filter(Boolean).join(' · ');
  return `<div class="swipe-card" data-id="${swipeEscape(talk.id)}"
  data-title="${swipeEscape(talk.title)}" data-paper="${swipeEscape(talk.paper)}"
  data-author="${swipeEscape(talk.author)}" data-abstract="${swipeEscape(talk.abstract || '')}"
  data-url="${swipeEscape(href)}" data-short="${swipeEscape(talk.short)}" data-color="${swipeEscape(talk.color)}"
  data-time="${swipeEscape(talk.time || '')}" data-room="${swipeEscape(talk.room || '')}"
  style="${style}">
  <div class="swipe-hint-skip">SKIP</div>
  <div class="swipe-hint-save">SAVE ★</div>
  <div class="swipe-card-conf" style="color:${talk.color}">${swipeEscape(talk.short)}</div>
  <div class="swipe-card-title"><span class="talk-link" onclick="openTalkModal(this)">${swipeEscape(talk.title)}</span></div>
  ${ metaParts.length ? `<div class="swipe-card-meta">${swipeEscape(metaParts.join(' · '))}</div>` : '' }
  ${ locationLine ? `<div class="swipe-card-meta" style="font-size:10px;opacity:.7">${swipeEscape(locationLine)}</div>` : '' }
  ${ talk.abstract ? `<div class="swipe-card-abstract">${swipeEscape(talk.abstract)}</div>` : '' }
</div>`;
}

function updateTalkSwipeArena() {
  const arena = document.getElementById('talkswipe-arena');
  const counter = document.getElementById('talkswipe-counter');
  arena.innerHTML = '';
  const remaining = talkSwipeQueue.length - talkSwipeIdx;
  counter.textContent = remaining + ' remaining';
  if (remaining === 0) {
    arena.innerHTML = '<div class="swipe-done"><strong>All done!</strong><br>Every talk in this filter has been reviewed.<br>Use the filters above or Reset to start again.</div>';
    return;
  }
  const preview = Math.min(3, remaining);
  for (let i = 0; i < preview; i++) {
    arena.innerHTML += renderTalkSwipeCard(talkSwipeQueue[talkSwipeIdx + i], i);
  }
  attachDragToTalkTop();
}

function applyTalkSwipeAction(action) {
  if (talkSwipeIdx >= talkSwipeQueue.length) return;
  const talk = talkSwipeQueue[talkSwipeIdx];
  const topCard = document.querySelector('#talkswipe-arena .swipe-card');
  talkSwipeHistory.push({ talk, action });

  const flyClass = action === 'save' ? 'fly-right' : 'fly-left';
  if (topCard) {
    topCard.classList.add(flyClass);
    setTimeout(() => { topCard.remove(); }, 380);
  }

  if (action === 'save') {
    bookmarks.add(talk.id);
    saveBookmarks();
    document.querySelectorAll('[data-id="' + CSS.escape(talk.id) + '"]').forEach(el => {
      el.classList.add('bookmarked');
      const star = el.querySelector('.star-btn, .poster-star-btn');
      if (star) star.textContent = '★';
    });
  } else {
    skipped.add(talk.id);
    saveSkipped();
    document.querySelectorAll('.talk-list-item[data-id="' + CSS.escape(talk.id) + '"]').forEach(el => {
      el.classList.add('skipped');
      const btn = el.querySelector('.talk-skip-btn');
      if (btn) btn.innerHTML = UNDO_ICON;
    });
  }

  talkSwipeIdx++;
  setTimeout(updateTalkSwipeArena, 80);
}

function undoTalkSwipe() {
  if (!talkSwipeHistory.length) return;
  const { talk, action } = talkSwipeHistory.pop();
  if (action === 'save') {
    bookmarks.delete(talk.id);
    saveBookmarks();
    document.querySelectorAll('[data-id="' + CSS.escape(talk.id) + '"]').forEach(el => {
      el.classList.remove('bookmarked');
      const star = el.querySelector('.star-btn, .poster-star-btn');
      if (star) star.textContent = '☆';
    });
  } else {
    skipped.delete(talk.id);
    saveSkipped();
    document.querySelectorAll('.talk-list-item[data-id="' + CSS.escape(talk.id) + '"]').forEach(el => {
      el.classList.remove('skipped');
      const btn = el.querySelector('.talk-skip-btn');
      if (btn) btn.textContent = '✕';
    });
  }
  talkSwipeIdx--;
  updateTalkSwipeArena();
}

function resetTalkSwipe() {
  buildTalkSwipeQueue();
  updateTalkSwipeArena();
}

function initTalkSwipe() {
  if (!talkSwipeInitialized) {
    talkSwipeInitialized = true;
    document.getElementById('talkswipe-filter-day').addEventListener('change', function() {
      talkSwipeFilterDay = this.value;
      resetTalkSwipe();
    });
    document.getElementById('talkswipe-filter-conf').addEventListener('change', function() {
      talkSwipeFilterConf = this.value;
      resetTalkSwipe();
    });
  }
  resetTalkSwipe();
}

function attachDragToTalkTop() {
  const card = document.querySelector('#talkswipe-arena .swipe-card');
  if (!card) return;
  let startX = 0, startY = 0, curX = 0, curY = 0;

  function onStart(x, y) {
    startX = x; startY = y; curX = x; curY = y;
    card.classList.add('dragging');
  }
  function onMove(x, y) {
    if (!card.classList.contains('dragging')) return;
    curX = x; curY = y;
    const dx = curX - startX;
    const dy = curY - startY;
    const rot = dx * 0.08;
    card.style.transform = `translate(${dx}px, ${dy}px) rotate(${rot}deg)`;
    card.querySelector('.swipe-hint-skip').style.opacity = Math.max(0, Math.min(1, -dx / 80));
    card.querySelector('.swipe-hint-save').style.opacity = Math.max(0, Math.min(1, dx / 80));
  }
  function onEnd() {
    if (!card.classList.contains('dragging')) return;
    card.classList.remove('dragging');
    const dx = curX - startX;
    if (dx > 80) applyTalkSwipeAction('save');
    else if (dx < -80) applyTalkSwipeAction('skip');
    else {
      card.style.transform = '';
      card.querySelector('.swipe-hint-skip').style.opacity = 0;
      card.querySelector('.swipe-hint-save').style.opacity = 0;
    }
  }

  card.addEventListener('mousedown', ev => { ev.preventDefault(); onStart(ev.clientX, ev.clientY); });
  window.addEventListener('mousemove', ev => onMove(ev.clientX, ev.clientY));
  window.addEventListener('mouseup', () => onEnd());

  card.addEventListener('touchstart', ev => { const t = ev.touches[0]; onStart(t.clientX, t.clientY); }, { passive: true });
  card.addEventListener('touchmove', ev => {
    const t = ev.touches[0];
    if (card.classList.contains('dragging')) ev.preventDefault();
    onMove(t.clientX, t.clientY);
  }, { passive: false });
  card.addEventListener('touchend', () => onEnd());
}

document.addEventListener('keydown', ev => {
  if (!document.getElementById('page-talkswipe').classList.contains('active')) return;
  if (ev.key === 'ArrowRight' || ev.key === 'l') applyTalkSwipeAction('save');
  else if (ev.key === 'ArrowLeft' || ev.key === 'h') applyTalkSwipeAction('skip');
  else if (ev.key === 'ArrowUp' || ev.key === 'u') undoTalkSwipe();
  else if (ev.key === 'ArrowDown' || ev.key === 'j') applyTalkSwipeAction('skip');
});

// ── Sync ──
const LS_SYNC_CODE = 'spie_as26_sync_code';
let syncCode = localStorage.getItem(LS_SYNC_CODE);
if (!syncCode) {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const raw = Array.from({length: 12}, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  syncCode = raw.slice(0,4) + '-' + raw.slice(4,8) + '-' + raw.slice(8,12);
  localStorage.setItem(LS_SYNC_CODE, syncCode);
}
let syncTimer = null;
let syncReady = false;
let lastPushTime = 0;

function setSyncStatus(status) {
  const icons  = {syncing:'↻', synced:'✓', error:'✕', idle:''};
  const colors = {syncing:'#7eb8f7', synced:'#3aaa8c', error:'#e15759', idle:'#888'};
  const titles = {syncing:'Syncing…', synced:'Synced', error:'Sync failed — check connection', idle:''};
  ['sync-status', 'sync-status-modal'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = icons[status] ?? '';
    el.style.color  = colors[status] ?? '';
    el.title = titles[status] ?? '';
  });
}

async function pushSync() {
  if (!SYNC_API) return;
  setSyncStatus('syncing');
  try {
    const res = await fetch(SYNC_API + '/sync/' + syncCode.replace(/-/g,''), {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({bookmarks:[...bookmarks], skipped:[...skipped]}),
    });
    if (!res.ok) throw new Error();
    lastPushTime = Date.now();
    setSyncStatus('synced');
  } catch { setSyncStatus('error'); }
}

function schedulePush() {
  if (!syncReady || !SYNC_API) return;
  setSyncStatus('syncing');
  clearTimeout(syncTimer);
  syncTimer = setTimeout(pushSync, 1500);
}

async function pullAndMerge(code) {
  const res = await fetch(SYNC_API + '/sync/' + code.replace(/-/g,''));
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const remote = await res.json();
  (remote.bookmarks || []).forEach(id => bookmarks.add(id));
  (remote.skipped   || []).forEach(id => skipped.add(id));
}

function updateSyncCodeDisplay() {
  const el = document.getElementById('sync-code-display');
  if (el) el.textContent = syncCode;
}

async function initSync() {
  if (!SYNC_API) { syncReady = true; updateSyncCodeDisplay(); return; }
  // Auto-link from ?sync=CODE URL parameter (shared link)
  const urlParam = new URLSearchParams(window.location.search).get('sync');
  if (urlParam) {
    const raw = urlParam.toUpperCase().replace(/-/g, '');
    if (/^[A-Z0-9]{12}$/.test(raw)) {
      const formatted = raw.slice(0,4) + '-' + raw.slice(4,8) + '-' + raw.slice(8,12);
      if (formatted !== syncCode) {
        syncCode = formatted;
        localStorage.setItem(LS_SYNC_CODE, syncCode);
      }
    }
    const clean = new URL(window.location);
    clean.searchParams.delete('sync');
    window.history.replaceState({}, '', clean);
  }
  updateSyncCodeDisplay();
  try {
    setSyncStatus('syncing');
    await pullAndMerge(syncCode);  // union-merge to preserve any offline local data
    saveBookmarks(false);
    saveSkipped(false);
    await pushSync();              // push merged state so lastPushTime is set correctly
    restoreBookmarks();
    restorePosterStates();
    restoreTalkListSkipped();
  } catch { setSyncStatus('idle'); }
  syncReady = true;
  startSyncPoll();
}
initSync();

async function bgPull() {
  if (!syncReady || !SYNC_API) return;
  try {
    const res = await fetch(SYNC_API + '/sync/' + syncCode.replace(/-/g,''));
    if (!res.ok) return;
    const remote = await res.json();
    if (!remote.updated_at || remote.updated_at <= lastPushTime) return;
    // Remote is newer than our last push — replace local state entirely
    bookmarks = new Set(remote.bookmarks || []);
    skipped   = new Set(remote.skipped   || []);
    saveBookmarks(false);
    saveSkipped(false);
    restoreBookmarks();
    restorePosterStates();
    restoreTalkListSkipped();
  } catch {}
}

function startSyncPoll() {
  if (!SYNC_API) return;
  setInterval(bgPull, 30000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') bgPull();
  });
}

function copySyncCode() {
  navigator.clipboard.writeText(syncCode).then(() => {
    document.getElementById('sync-notice').textContent = 'Code copied!';
  });
}

function copySyncLink() {
  const url = new URL(window.location.href);
  url.searchParams.set('sync', syncCode);
  navigator.clipboard.writeText(url.toString()).then(() => {
    document.getElementById('sync-notice').textContent = 'Link copied — open it on another device to sync!';
  });
}

async function linkDevice() {
  const raw = document.getElementById('link-code-input').value.trim().toUpperCase().replace(/-/g,'');
  if (!/^[A-Z0-9]{12}$/.test(raw)) {
    document.getElementById('sync-notice').textContent = 'Invalid code — should be XXXX-XXXX-XXXX.';
    return;
  }
  const formatted = raw.slice(0,4) + '-' + raw.slice(4,8) + '-' + raw.slice(8,12);
  document.getElementById('sync-notice').textContent = 'Linking…';
  try {
    setSyncStatus('syncing');
    await pullAndMerge(formatted);
    syncCode = formatted;
    localStorage.setItem(LS_SYNC_CODE, syncCode);
    updateSyncCodeDisplay();
    saveBookmarks(false);
    saveSkipped(false);
    restoreBookmarks();
    restorePosterStates();
    restoreTalkListSkipped();
    await pushSync();
    document.getElementById('sync-notice').textContent = 'Linked! Both devices now share this code.';
    document.getElementById('link-code-input').value = '';
  } catch {
    document.getElementById('sync-notice').textContent = 'Could not reach the server — try again.';
    setSyncStatus('error');
  }
}

// ── Talk detail modal ──
let talkModalId = null;

function openTalkModal(el) {
  const card = el.closest('[data-id]');
  const d = card.dataset;
  talkModalId = d.id;
  document.getElementById('talk-modal-conf').textContent = d.short || '';
  document.getElementById('talk-modal-conf').style.color = d.color || '#999';
  document.getElementById('talk-modal-title').textContent = d.title || '';
  const meta = [];
  if (d.dayLabel) meta.push(d.dayLabel);
  if (d.paper) meta.push('[' + d.paper + ']');
  if (d.time) meta.push(d.time);
  if (d.room && d.room !== 'Room TBC') meta.push(d.room);
  document.getElementById('talk-modal-meta').textContent = meta.join(' · ');
  const td = TALK_DATA[d.id] || {};
  document.getElementById('talk-modal-authors').textContent = td.authors || d.author || '';
  document.getElementById('talk-modal-abstract').textContent =
    td.abstract || 'No abstract available.';
  const ext = document.getElementById('talk-modal-ext');
  ext.href = d.url || '#';
  ext.style.display = d.url ? '' : 'none';
  updateModalBookmarkBtn();
  document.getElementById('talk-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function updateModalBookmarkBtn() {
  const btn = document.getElementById('talk-modal-star');
  if (!btn || !talkModalId) return;
  const saved = bookmarks.has(talkModalId);
  btn.innerHTML = saved ? '&#9733; Saved' : '&#9734; Save to schedule';
  btn.style.color = saved ? '#f5a623' : '';
  btn.style.borderColor = saved ? '#f5a623' : '#ccc';
}

function toggleModalBookmark() {
  if (!talkModalId) return;
  const wasBookmarked = bookmarks.has(talkModalId);
  if (wasBookmarked) { bookmarks.delete(talkModalId); } else { bookmarks.add(talkModalId); }
  document.querySelectorAll('[data-id="' + CSS.escape(talkModalId) + '"]').forEach(el => {
    el.classList.toggle('bookmarked', !wasBookmarked);
    const star = el.querySelector('.star-btn, .poster-star-btn');
    if (star) star.textContent = wasBookmarked ? '☆' : '★';
  });
  saveBookmarks();
  updateBookmarkCount();
  updateModalBookmarkBtn();
}

function closeTalkModal() {
  document.getElementById('talk-modal').classList.remove('open');
  document.body.style.overflow = '';
  talkModalId = null;
}

document.getElementById('talk-modal').addEventListener('click', ev => {
  if (ev.target === document.getElementById('talk-modal')) closeTalkModal();
});

document.addEventListener('keydown', ev => {
  if (ev.key === 'Escape') closeTalkModal();
});
"""




def render_swipe_page(poster_days: list[dict]) -> str:
    day_opts = "".join(
        f'<option value="{d["date_iso"]}">{e(d["label"])}</option>' for d in poster_days
    )
    conf_opts = "".join(
        f'<option value="{conf}">{e(CONF_SHORT.get(conf, conf))}</option>'
        for conf in sorted(CONFERENCES_OF_INTEREST)
    )
    return (
        f'<div class="swipe-controls">'
        f'<span class="swipe-filter-label">Day:</span>'
        f'<select class="swipe-filter-select" id="swipe-filter-day">'
        f'<option value="all">All days</option>{day_opts}</select>'
        f'<span class="swipe-filter-label">Track:</span>'
        f'<select class="swipe-filter-select" id="swipe-filter-conf">'
        f'<option value="all">All tracks</option>{conf_opts}</select>'
        f'<span class="swipe-counter" id="swipe-counter"></span>'
        f"</div>"
        f'<div class="swipe-arena" id="swipe-arena"></div>'
        f'<div class="swipe-btn-row">'
        f'<button class="swipe-action-btn skip-btn" onclick="applySwipeAction(\'skip\')">&#10005;</button>'
        f'<button class="swipe-action-btn undo-btn" onclick="undoSwipe()">{UNDO_SVG}</button>'
        f'<button class="swipe-action-btn save-btn" onclick="applySwipeAction(\'save\')">&#9733;</button>'
        f"</div>"
        f'<div class="swipe-keys">&#8592; skip &nbsp;|&nbsp; &#8594; save &nbsp;|&nbsp; &#8593; undo</div>'
    )



def render_talk_swipe_page(days: list[dict]) -> str:
    day_opts = "".join(
        f'<option value="{d["date_iso"]}">{e(d["label"])}</option>' for d in days
    )
    conf_opts = "".join(
        f'<option value="{conf}">{e(CONF_SHORT.get(conf, conf))}</option>'
        for conf in sorted(CONF_SHORT)
    )
    return (
        f'<div class="swipe-controls">'
        f'<span class="swipe-filter-label">Day:</span>'
        f'<select class="swipe-filter-select" id="talkswipe-filter-day">'
        f'<option value="all">All days</option>{day_opts}</select>'
        f'<span class="swipe-filter-label">Track:</span>'
        f'<select class="swipe-filter-select" id="talkswipe-filter-conf">'
        f'<option value="all">All tracks</option>{conf_opts}</select>'
        f'<span class="swipe-counter" id="talkswipe-counter"></span>'
        f"</div>"
        f'<div class="swipe-arena" id="talkswipe-arena"></div>'
        f'<div class="swipe-btn-row">'
        f'<button class="swipe-action-btn skip-btn" onclick="applyTalkSwipeAction(\'skip\')">&#10005;</button>'
        f'<button class="swipe-action-btn undo-btn" onclick="undoTalkSwipe()">{UNDO_SVG}</button>'
        f'<button class="swipe-action-btn save-btn" onclick="applyTalkSwipeAction(\'save\')">&#9733;</button>'
        f"</div>"
        f'<div class="swipe-keys">&#8592; skip &nbsp;|&nbsp; &#8594; save &nbsp;|&nbsp; &#8593; undo</div>'
    )


def build_html(days: list[dict], poster_days: list[dict], records: list[dict]) -> str:
    legend = "".join(
        f'<span class="legend-item" data-conf="{e(c)}" onclick="toggleConfFilter(\'{e(c)}\')">'
        f'<span class="legend-dot" style="background:{CONF_COLOR.get(c, "#999")}"></span>'
        f"{e(CONF_SHORT.get(c, c))}</span>"
        for c in sorted(CONF_SHORT)
    )
    legend += '<button id="clear-conf-btn" onclick="clearConfFilters()" style="display:none">&#10005; Clear filters</button>'

    view_nav = (
        '<nav class="view-nav">'
        '<button class="view-nav-toggle" onclick="toggleViewMenu()">'
        '<span id="view-current-label">Talk Schedule</span>'
        '<span class="view-nav-arrow">&#9660;</span>'
        "</button>"
        '<button class="view-btn active" data-view="schedule" onclick="switchView(\'schedule\')">Talk Schedule</button>'
        '<button class="view-btn" data-view="talklist" onclick="switchView(\'talklist\')">Talk List</button>'
        f'<button class="view-btn" data-view="talkswipe" onclick="switchView(\'talkswipe\')">{TINDER_SVG}Talk Swipe</button>'
        '<span class="view-nav-divider"></span>'
        '<button class="view-btn" data-view="posters" onclick="switchView(\'posters\')">Poster List</button>'
        f'<button class="view-btn" data-view="swipe" onclick="switchView(\'swipe\')">{TINDER_SVG}Poster Swipe</button>'
        "</nav>"
    )

    talkswipe_html = render_talk_swipe_page(days)
    swipe_html = render_swipe_page(poster_days)

    _dumps = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    full_js = (
        f"const SYNC_API = {repr(SYNC_API_URL)};\n"
        f"const TALK_DATA = {_dumps(build_talk_data(records))};\n"
        f"const ALL_DAYS = {_dumps(serialize_days(days))};\n"
        f"const ALL_POSTER_DAYS = {_dumps(serialize_poster_days(poster_days))};\n"
        f"const CONF_COLOR = {_dumps(CONF_COLOR)};\n"
        f"const CONF_SHORT = {_dumps(CONF_SHORT)};\n"
        + JS
        + RENDER_JS
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
    <input id="search" type="search" placeholder="Search talks: title, author, paper…" autocomplete="off">
    <button id="clear-btn" onclick="clearSearch()">Clear</button>
  </div>
  <button id="my-schedule-btn" onclick="toggleMySchedule()">&#9733; My Schedule</button>
  <span id="bookmark-count"></span>
  <button id="share-btn" onclick="openShareModal()">&#8645; Sync &amp; Backup</button>
  <span id="sync-status" style="font-size:13px;min-width:16px;text-align:center;cursor:default;transition:color .3s" title=""></span>
  <span id="match-count"></span>
  <a href="https://github.com/ppp-one/spie-astronomy-schedule" target="_blank" rel="noopener" class="github-link" title="View on GitHub" style="margin-left:auto;color:#7eb8f7;display:flex;align-items:center;text-decoration:none;">
    <svg height="20" width="20" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
  </a>
</div>

<div class="legend">{legend}</div>
{view_nav}
<div class="page active" id="page-schedule">
<div id="schedule-body">
<div class="tabs" id="schedule-tabs"></div>
</div>
</div>
<div class="page" id="page-talklist">
<div id="talklist-body"></div>
</div>
<div class="page" id="page-posters">
<div id="poster-body"></div>
</div>
<div class="page" id="page-talkswipe">
<div id="talkswipe-body">
{talkswipe_html}
</div>
</div>
<div class="page" id="page-swipe">
<div id="swipe-body">
{swipe_html}
</div>
</div>

<div class="modal-backdrop" id="share-modal">
  <div class="modal">
    <h2>&#8645; Sync &amp; Backup</h2>

    <p style="font-size:11px;font-weight:700;color:#888;letter-spacing:.05em;margin:0 0 6px">CROSS-DEVICE SYNC</p>
    <p style="font-size:12px;color:#555;margin:0 0 8px;line-height:1.5">Share this link with another device — opening it will instantly sync your bookmarks and skipped items:</p>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <code id="sync-code-display" style="font-size:20px;font-weight:700;letter-spacing:.12em;color:#1a1a2e;background:#f0f2f5;padding:7px 14px;border-radius:6px;flex:1;text-align:center">····-····-····</code>
      <span id="sync-status-modal" style="font-size:14px;min-width:18px;text-align:center"></span>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="modal-btn primary" onclick="copySyncLink()">Copy Link</button>
      <button class="modal-btn secondary" onclick="copySyncCode()">Copy Code</button>
    </div>
    <p style="font-size:12px;color:#555;margin:0 0 6px">Or link by entering another device's code manually:</p>
    <div style="display:flex;gap:8px;margin-bottom:4px">
      <input id="link-code-input" placeholder="XXXX-XXXX-XXXX" maxlength="14"
        style="flex:1;padding:6px 10px;border:1px solid #ccc;border-radius:4px;font-size:14px;font-family:monospace;text-transform:uppercase;letter-spacing:.08em">
      <button class="modal-btn primary" onclick="linkDevice()">Link</button>
    </div>
    <div class="modal-notice" id="sync-notice"></div>

    <hr style="margin:16px 0;border:none;border-top:1px solid #eee">

    <p style="font-size:11px;font-weight:700;color:#888;letter-spacing:.05em;margin:0 0 6px">MANUAL BACKUP</p>
    <p style="font-size:12px;color:#555;margin:0 0 8px;line-height:1.5">Copy as a plain-text backup in case you lose your sync code:</p>
    <textarea id="export-code" readonly placeholder="(no bookmarks saved yet)"></textarea>
    <div class="modal-row">
      <button class="modal-btn primary" onclick="copyExport()">Copy to clipboard</button>
      <button class="modal-btn danger" onclick="clearAllBookmarks()">Clear all</button>
      <button class="modal-btn secondary" onclick="closeShareModal()">Close</button>
    </div>
    <p style="margin-top:16px;margin-bottom:4px;font-size:12px;color:#555">Restore from a backup:</p>
    <textarea id="import-code" placeholder="Paste backup here…"></textarea>
    <div class="modal-row">
      <button class="modal-btn primary" onclick="importBookmarks()">Restore</button>
    </div>
    <div class="modal-notice" id="share-notice"></div>
  </div>
</div>

<div class="modal-backdrop" id="talk-modal">
  <div class="modal" style="max-width:640px">
    <button class="modal-close" onclick="closeTalkModal()">&#10005;</button>
    <span id="talk-modal-conf"></span>
    <h2 id="talk-modal-title"></h2>
    <p id="talk-modal-meta" style="margin:0 0 4px"></p>
    <p id="talk-modal-authors" style="font-size:12px;color:#555;margin:0 0 14px;line-height:1.5"></p>
    <p id="talk-modal-abstract"></p>
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <button id="talk-modal-star" onclick="toggleModalBookmark()"
        style="background:none;border:1px solid #ccc;border-radius:4px;padding:5px 12px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:5px">
        &#9734; Save to schedule
      </button>
      <a id="talk-modal-ext" href="#" target="_blank" rel="noopener">Open on SPIE &#8599;</a>
    </div>
  </div>
</div>

<script>{full_js}</script>
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
    days = build_days(records)
    poster_days = build_poster_days(records)
    html = build_html(days, poster_days, records)
    out = OUTPUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Written → {out}")
    for d in days:
        total = sum(len(v) for v in d["rooms_map"].values())
        print(f"  {d['label']}: {total} talks across {len(d['rooms'])} rooms")
    total_posters = sum(
        sum(len(v) for v in d["confs_map"].values()) for d in poster_days
    )
    print(f"  {total_posters} poster entries across {len(poster_days)} days")


if __name__ == "__main__":
    main()
