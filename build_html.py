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
from itertools import groupby
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
        f'data-authors="{e(talk.get("authors", talk["author"]))}" '
        f'data-abstract="{e(talk["abstract"] or "")}" '
        f'data-url="{e(href)}" '
        f'data-conf="{e(talk["conf"])}" '
        f'data-short="{e(short)}" '
        f'data-color="{color}" '
        f'data-time="{e(time_label)}" '
        f'data-room="{e(talk["room"])}"'
    )


def render_cal_card(talk: dict, top: int, height: int) -> str:
    color = CONF_COLOR.get(talk["conf"], "#999")
    short = CONF_SHORT.get(talk["conf"], talk["conf"])
    search = e(f"{talk['title']} {talk['paper']} {talk['author']} {talk['abstract']}")
    href = f"https://spie.org{talk['url']}" if talk.get("url") else ""
    card_id = e(talk["paper"] if talk["paper"] else f"PLENARY-{talk['title']}")

    if talk["conf"] == "PLENARY":
        card_style = (
            f"background:#1a1a2e;border-left-color:#fff;top:{top}px;height:{height}px"
        )
        conf_color = "color:#fff"
        title_color = "color:#fff"
    else:
        card_style = f"border-left-color:{color};top:{top}px;height:{height}px"
        conf_color = f"color:{color}"
        title_color = ""

    title_html = f'<span class="talk-link" onclick="openTalkModal(this)">{e(talk["title"])}</span>'
    meta = (
        f'<div class="talk-meta">[{e(talk["paper"])}] {e(talk["author"])}</div>'
        if talk["conf"] != "PLENARY"
        else ""
    )

    return (
        f'<div class="talk cal-talk" data-search="{search}" data-id="{card_id}" '
        f'{_modal_data(talk, href, short, color)} style="{card_style}">'
        f'<div class="talk-header">'
        f'<span class="talk-conf" style="{conf_color}">{e(short)}</span>'
        f'<button class="star-btn" onclick="toggleBookmark(this)" title="Save to My Schedule">☆</button>'
        f"</div>"
        f'<div class="talk-title" style="{title_color}">{title_html}</div>'
        f"{meta}"
        f"</div>"
    )


def render_session_item(talk: dict) -> str:
    color = CONF_COLOR.get(talk["conf"], "#999")
    short = CONF_SHORT.get(talk["conf"], talk["conf"])
    search = e(f"{talk['title']} {talk['paper']} {talk['author']} {talk['abstract']}")
    href = f"https://spie.org{talk['url']}" if talk.get("url") else ""
    card_id = e(talk["paper"] if talk["paper"] else f"PLENARY-{talk['title']}")
    title_html = f'<span class="talk-link" onclick="openTalkModal(this)">{e(talk["title"])}</span>'
    meta = (
        f'<div class="talk-meta">[{e(talk["paper"])}] {e(talk["author"])}</div>'
        if talk["conf"] != "PLENARY"
        else ""
    )
    return (
        f'<div class="talk session-item" data-search="{search}" data-id="{card_id}" '
        f'{_modal_data(talk, href, short, color)} style="border-left-color:{color}">'
        f'<div class="talk-header">'
        f'<span class="talk-conf" style="color:{color}">{e(short)}</span>'
        f'<button class="star-btn" onclick="toggleBookmark(this)" title="Save to My Schedule">☆</button>'
        f"</div>"
        f'<div class="talk-title">{title_html}</div>'
        f"{meta}"
        f"</div>"
    )


def render_session_block(
    talks: list[dict], top: int, height: int, talk_start: int, talk_end: int
) -> str:
    label = (
        f"{talk_start // 60:02d}:{talk_start % 60:02d}"
        f"–{talk_end // 60:02d}:{talk_end % 60:02d} CEST"
    )
    items = "".join(render_session_item(t) for t in talks)
    return (
        f'<div class="cal-session" style="top:{top}px;height:{height}px">'
        f'<div class="session-header">'
        f"<span>{e(label)}</span>"
        f"<span>{len(talks)} talks</span>"
        f"</div>"
        f'<div class="session-list">{items}</div>'
        f"</div>"
    )


def render_agenda_day(day: dict) -> str:
    """Flat chronological agenda list used in the mobile calendar view."""
    all_talks: list[dict] = []
    for talks in day["rooms_map"].values():
        all_talks.extend(talks)
    all_talks.sort(key=lambda t: (to_minutes(t["time_sort"]), t["room"], t["title"]))

    rows: list[str] = []
    last_hour = -1

    for talk in all_talks:
        start_min = to_minutes(talk["time_sort"])
        hour = start_min // 60

        if hour != last_hour:
            last_hour = hour
            rows.append(
                f'<div class="agenda-hour-sep" style="top:var(--tabs-h,0)">'
                f"<span>{hour:02d}:00</span>"
                f"</div>"
            )

        end_str = slot_end(talk["time_slot"])
        color = CONF_COLOR.get(talk["conf"], "#999")
        short = CONF_SHORT.get(talk["conf"], talk["conf"])
        search = e(
            f"{talk['title']} {talk['paper']} {talk['author']} {talk['abstract']}"
        )
        href = f"https://spie.org{talk['url']}" if talk.get("url") else ""
        card_id = e(talk["paper"] if talk["paper"] else f"PLENARY-{talk['title']}")

        title_html = f'<span class="talk-link" onclick="openTalkModal(this)">{e(talk["title"])}</span>'
        end_html = (
            f'<span class="agenda-time-end">{e(end_str)}</span>' if end_str else ""
        )
        meta_parts = [
            p for p in [talk["room"], talk["author"]] if p and p != "Room TBC"
        ]
        meta_html = " · ".join(e(p) for p in meta_parts)

        plenary = talk["conf"] == "PLENARY"
        row_cls = " agenda-row--plenary" if plenary else ""
        star_color = "color:#7eb8f7" if plenary else ""

        rows.append(
            f'<div class="agenda-row talk{row_cls}" '
            f'data-search="{search}" data-id="{card_id}" '
            f'{_modal_data(talk, href, short, color)} style="border-left-color:{color}">'
            f'<div class="agenda-time-col">'
            f'<span class="agenda-time-start">{start_min // 60:02d}:{start_min % 60:02d}</span>'
            f"{end_html}"
            f"</div>"
            f'<div class="agenda-event-col">'
            f'<span class="agenda-conf" style="color:{color}">{e(short)}</span>'
            f'<div class="agenda-title">{title_html}</div>'
            f"{'<div class="agenda-meta">' + meta_html + '</div>' if meta_html else ''}"
            f"</div>"
            f'<button class="star-btn" onclick="toggleBookmark(this)" '
            f'title="Save to My Schedule" style="{star_color}">&#9734;</button>'
            f"</div>"
        )

    return f'<div class="cal-agenda">{"".join(rows)}</div>'


def render_calendar_day(day: dict) -> str:
    start_min = day["day_start_min"]
    end_min = day["day_end_min"]
    total_min = end_min - start_min
    total_px = total_min * PX_MIN
    rooms = day["rooms"]
    rooms_map = day["rooms_map"]

    # Time gutter labels and grid lines every 30 minutes
    marks = []
    lines = []
    for offset in range(0, total_min + 1, 30):
        top = offset * PX_MIN
        abs_min = start_min + offset
        label = f"{abs_min // 60:02d}:{abs_min % 60:02d}"
        # First mark: don't pull up with translateY(-50%) or it clips behind the header
        extra = " first-mark" if offset == 0 else ""
        marks.append(f'<div class="cal-mark{extra}" style="top:{top}px">{label}</div>')
        cls = "cal-hour-line" if abs_min % 60 == 0 else "cal-half-line"
        lines.append(f'<div class="{cls}" style="top:{top}px"></div>')

    # Poster session background band
    if POSTER_START_MIN >= start_min and POSTER_START_MIN < end_min:
        p_top = (POSTER_START_MIN - start_min) * PX_MIN
        p_h = (min(POSTER_END_MIN, end_min) - POSTER_START_MIN) * PX_MIN
        lines.append(
            f'<div class="cal-poster-band" style="top:{p_top}px;height:{p_h}px"></div>'
        )

    # Room columns — group talks by identical time bounds so concurrent talks
    # (e.g. poster sessions) are rendered as a scrollable block, not stacked cards.
    cols = []
    for room in rooms:
        cards = []
        sorted_talks = sorted(rooms_map[room], key=talk_time_bounds)
        for (ts, te), grp in groupby(sorted_talks, key=talk_time_bounds):
            group = list(grp)
            top = (ts - start_min) * PX_MIN
            height = max(te - ts, 5) * PX_MIN
            if len(group) == 1:
                cards.append(render_cal_card(group[0], top, height))
            else:
                cards.append(render_session_block(group, top, height, ts, te))
        cols.append(f'<div class="cal-col">{"".join(cards)}</div>')

    timeline_w = len(rooms) * ROOM_COL_W
    room_heads = "".join(f'<div class="cal-room-head">{e(r)}</div>' for r in rooms)

    grid = (
        f'<div class="cal-wrap">'
        f'<div class="cal-header-row">'
        f'<div class="cal-gutter-ph"></div>'
        f"{room_heads}"
        f"</div>"
        f'<div class="cal-body">'
        f'<div class="cal-gutter" style="height:{total_px}px">{"".join(marks)}</div>'
        f'<div class="cal-timeline" style="height:{total_px}px;width:{timeline_w}px">'
        f"{''.join(lines)}"
        f'<div class="cal-cols">{"".join(cols)}</div>'
        f"</div>"
        f"</div>"
        f"</div>"
    )
    return grid + render_agenda_day(day)


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
.talk-link {
  color: inherit;
  text-decoration: none;
  cursor: pointer;
}
.talk-link:hover { text-decoration: underline; }
/* ── Talk detail modal ── */
#talk-modal .modal { max-width: 640px; max-height: 90vh; overflow-y: auto; }
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
  padding-right: 24px;
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
#poster-star-count { font-size: 11px; color: #f5a623; padding: 4px 16px 6px; display: block; }
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
.swipe-action-btn.undo-btn  { width: 44px; height: 44px; border-width: 1px; border-style: dashed; border-color: #556; color: #7eb8f7; font-size: 20px; }
.swipe-action-btn.undo-btn:hover  { border-color: #7eb8f7; background: rgba(126,184,247,.15); }
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
  .view-nav { padding: 0 8px; }
  .view-btn { font-size: 12px; padding: 7px 10px; }
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
  .swipe-action-btn.undo-btn { width: 38px; height: 38px; font-size: 18px; }
  .swipe-keys { display: none; }
  .swipe-btn-row { gap: 20px; }
}
"""

JS = """
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
  applyConfFilter();
  applySearch();
}

function applyConfFilter() {
  document.querySelectorAll('.talk, .talk-list-item, .poster-item').forEach(el => {
    el.classList.toggle('conf-hidden',
      confFilters.size > 0 && !confFilters.has(el.dataset.conf));
  });
}

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
    if (bookmarks.has(card.dataset.id)) {
      card.classList.add('bookmarked');
      card.querySelector('.star-btn').textContent = '★';
    }
  });
}

function toggleMySchedule() {
  myScheduleActive = !myScheduleActive;
  document.body.classList.toggle('my-schedule-mode', myScheduleActive);
  const btn = document.getElementById('my-schedule-btn');
  btn.classList.toggle('active', myScheduleActive);
  btn.textContent = myScheduleActive ? '★ All talks' : '★ My Schedule';
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
  document.querySelectorAll('.day-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('day-' + iso).style.display = 'block';
  document.querySelector('[data-day="' + iso + '"]').classList.add('active');
  applySearch();
}

function applySearch() {
  const q = document.getElementById('search').value.toLowerCase().trim();
  let n = 0;

  if (document.getElementById('page-talklist').classList.contains('active')) {
    const panel = document.querySelector('.talk-list-day-panel.active');
    if (panel) {
      panel.querySelectorAll('.talk-list-item').forEach(t => {
        const searchOk = !q || t.dataset.search.toLowerCase().includes(q);
        const scheduleOk = !myScheduleActive || t.classList.contains('bookmarked');
        const visible = searchOk && scheduleOk;
        t.style.display = visible ? '' : 'none';
        if (visible && q && !t.classList.contains('conf-hidden')) n++;
      });
    }
    document.getElementById('match-count').textContent =
      q ? n + ' match' + (n !== 1 ? 'es' : '') : '';
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
  document.documentElement.style.setProperty('--topbar-h', topbarH + 'px');
  const tabsEl = document.querySelector('#schedule-body .tabs');
  if (tabsEl) {
    document.documentElement.style.setProperty('--tabs-h', tabsEl.offsetHeight + 'px');
  }
  const posterTabsEl = document.querySelector('#poster-body .tabs');
  if (posterTabsEl) {
    document.documentElement.style.setProperty('--poster-tabs-h', posterTabsEl.offsetHeight + 'px');
  }
  const body = document.getElementById('schedule-body');
  if (body) body.style.height = (window.innerHeight - topbarH) + 'px';
  const posterBody = document.getElementById('poster-body');
  if (posterBody) posterBody.style.height = (window.innerHeight - topbarH) + 'px';
  const swipeBody = document.getElementById('swipe-body');
  if (swipeBody) swipeBody.style.height = (window.innerHeight - topbarH) + 'px';
  const talkswipeBody = document.getElementById('talkswipe-body');
  if (talkswipeBody) talkswipeBody.style.height = (window.innerHeight - topbarH) + 'px';
}
updateStickyOffset();
window.addEventListener('resize', updateStickyOffset);

restoreBookmarks();
updateBookmarkCount();

// ── Export / Import ──
function openShareModal() {
  document.getElementById('export-code').value =
    JSON.stringify([...bookmarks], null, 2) || '';
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
    c.querySelector('.star-btn').textContent = '☆';
  });
  document.getElementById('export-code').value = '';
  document.getElementById('share-notice').textContent = 'All bookmarks cleared.';
}

document.getElementById('share-modal').addEventListener('click', ev => {
  if (ev.target === ev.currentTarget) closeShareModal();
});

// ── View switcher ──
function switchView(view) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + view).classList.add('active');
  document.querySelector('[data-view="' + view + '"]').classList.add('active');
  updateStickyOffset();
  if (view === 'swipe') initSwipe();
  if (view === 'talkswipe') initTalkSwipe();
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
  document.querySelectorAll('.talk-list-day-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('#talklist-body .tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('talklist-day-' + iso).classList.add('active');
  document.querySelector('#talklist-body [data-day="' + iso + '"]').classList.add('active');
  applySearch();
}

// ── Poster page ──
const LS_SKIP = 'spie_as26_skipped';
let skipped = new Set(JSON.parse(localStorage.getItem(LS_SKIP) || '[]'));

function saveSkipped() {
  localStorage.setItem(LS_SKIP, JSON.stringify([...skipped]));
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
    btn.textContent = '↩';
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
  document.querySelectorAll('.poster-day-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('#poster-body .tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('poster-day-' + iso).classList.add('active');
  document.querySelector('#poster-body [data-day="' + iso + '"]').classList.add('active');
  applyPosterSearch();
}

function applyPosterSearch() {
  const q = document.getElementById('search').value.toLowerCase().trim();
  const panel = document.querySelector('.poster-day-panel.active');
  if (!panel) return;
  let matchCount = 0, total = 0, starred = 0;
  panel.querySelectorAll('.poster-item').forEach(item => {
    const text = item.dataset.search.toLowerCase();
    const searchOk = !q || text.includes(q);
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
    btn.textContent = '↩';
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
    if (skipped.has(item.dataset.id)) {
      item.classList.add('skipped');
      const btn = item.querySelector('.talk-skip-btn');
      if (btn) btn.textContent = '↩';
    }
  });
}
restoreTalkListSkipped();

function restorePosterStates() {
  document.querySelectorAll('.poster-item').forEach(item => {
    const id = item.dataset.id;
    if (bookmarks.has(id)) {
      item.classList.add('bookmarked');
      item.querySelector('.poster-star-btn').textContent = '★';
    }
    if (skipped.has(id)) {
      item.classList.add('skipped');
      item.querySelector('.poster-skip-btn').textContent = '↩';
    }
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
  const allCards = Array.from(document.querySelectorAll('.swipe-card-data'));
  swipeQueue = allCards
    .filter(el => {
      if (swipeFilterDay !== 'all' && el.dataset.day !== swipeFilterDay) return false;
      if (swipeFilterConf !== 'all' && el.dataset.conf !== swipeFilterConf) return false;
      return !bookmarks.has(el.dataset.id) && !skipped.has(el.dataset.id);
    })
    .map(el => ({
      id: el.dataset.id,
      conf: el.dataset.conf,
      day: el.dataset.day,
      title: el.dataset.title,
      paper: el.dataset.paper,
      author: el.dataset.author,
      abstract: el.dataset.abstract,
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
      pItem.querySelector('.poster-skip-btn').textContent = '↩';
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
  const allCards = Array.from(document.querySelectorAll('.talk-swipe-card-data'));
  const seen = new Set();
  talkSwipeQueue = allCards
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
      title: el.dataset.title,
      paper: el.dataset.paper,
      author: el.dataset.author,
      abstract: el.dataset.abstract,
      url: el.dataset.url,
      color: el.dataset.color,
      short: el.dataset.short,
      time: el.dataset.time,
      room: el.dataset.room,
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
  ${ timeMeta ? `<div class="swipe-card-meta" style="font-size:10px;opacity:.7">${swipeEscape(timeMeta)}</div>` : '' }
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
      if (btn) btn.textContent = '↩';
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
  if (d.paper) meta.push('[' + d.paper + ']');
  if (d.time) meta.push(d.time);
  if (d.room && d.room !== 'Room TBC') meta.push(d.room);
  document.getElementById('talk-modal-meta').textContent = meta.join(' · ');
  document.getElementById('talk-modal-authors').textContent = d.authors || d.author || '';
  document.getElementById('talk-modal-abstract').textContent =
    d.abstract || 'No abstract available.';
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


def render_poster_page(poster_days: list[dict]) -> str:
    if not poster_days:
        return '<div style="padding:32px;color:#888">No poster sessions found.</div>'

    # Build all items once; day panels are subsets
    all_items: list[str] = []
    day_items: dict[str, list[str]] = {}
    for d in poster_days:
        day_list: list[str] = []
        for conf, talks in d["confs_map"].items():
            color = CONF_COLOR.get(conf, "#999")
            short = CONF_SHORT.get(conf, conf)
            for t in talks:
                card_id = e(t["paper"])
                href = f"https://spie.org{t['url']}" if t.get("url") else ""
                title_html = f'<span class="talk-link" onclick="openTalkModal(this)">{e(t["title"])}</span>'
                search_text = e(
                    f"{t['title']} {t['paper']} {t['author']} {t['abstract']}"
                )
                item = (
                    f'<div class="poster-item" data-id="{card_id}" data-search="{search_text}" '
                    f"{_modal_data(t, href, short, color)}>"
                    f'<div class="poster-item-body">'
                    f'<div class="poster-item-title">{title_html}</div>'
                    f'<div class="poster-item-meta">'
                    f'<span class="poster-item-conf" style="color:{color}">{e(short)}</span>'
                    f" &middot; [{e(t['paper'])}] {e(t['author'])}"
                    f"</div>"
                    f"</div>"
                    f'<div class="poster-actions">'
                    f'<button class="poster-skip-btn" onclick="togglePosterSkip(this)" title="Not interested">&#10005;</button>'
                    f'<button class="poster-star-btn" onclick="togglePosterBookmark(this)" title="Save to My Schedule">&#9734;</button>'
                    f"</div>"
                    f"</div>"
                )
                day_list.append(item)
                all_items.append(item)
        day_items[d["date_iso"]] = day_list

    tabs = (
        '<button class="tab-btn active" data-day="all" onclick="switchPosterDay(\'all\')" '
        'style="font-size:12px;padding:5px 14px">All days</button>'
    )
    tabs += "".join(
        f'<button class="tab-btn" '
        f'data-day="{d["date_iso"]}" onclick="switchPosterDay(\'{d["date_iso"]}\')" '
        f'style="font-size:12px;padding:5px 14px">'
        f"{e(d['label'])}</button>"
        for d in poster_days
    )

    all_panel = (
        '<div class="poster-day-panel active" id="poster-day-all">'
        + "".join(all_items)
        + "</div>"
    )
    day_panels = "".join(
        f'<div class="poster-day-panel" id="poster-day-{d["date_iso"]}">'
        + "".join(day_items[d["date_iso"]])
        + "</div>"
        for d in poster_days
    )

    star_count = '<span id="poster-star-count"></span>'
    return f'<div class="tabs">{tabs}</div>' + star_count + all_panel + day_panels


def render_swipe_data(poster_days: list[dict]) -> str:
    """Hidden elements carrying poster metadata for the swipe game JS."""
    parts = []
    for d in poster_days:
        for conf, talks in d["confs_map"].items():
            color = CONF_COLOR.get(conf, "#999")
            short = CONF_SHORT.get(conf, conf)
            for t in talks:
                parts.append(
                    f'<span class="swipe-card-data" '
                    f'data-id="{e(t["paper"])}" '
                    f'data-day="{e(d["date_iso"])}" '
                    f'data-conf="{e(conf)}" '
                    f'data-title="{e(t["title"])}" '
                    f'data-paper="{e(t["paper"])}" '
                    f'data-author="{e(t["author"])}" '
                    f'data-abstract="{e(t["abstract"])}" '
                    f'data-url="{e(t["url"])}" '
                    f'data-color="{color}" '
                    f'data-short="{e(short)}"></span>'
                )
    return '<div id="swipe-data" style="display:none">' + "".join(parts) + "</div>"


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
        f'<button class="swipe-action-btn undo-btn" onclick="undoSwipe()">&#8630;</button>'
        f'<button class="swipe-action-btn save-btn" onclick="applySwipeAction(\'save\')">&#9733;</button>'
        f"</div>"
        f'<div class="swipe-keys">&#8592; skip &nbsp;|&nbsp; &#8594; save &nbsp;|&nbsp; &#8593; undo</div>'
    )


def render_talk_swipe_data(days: list[dict]) -> str:
    """Hidden spans carrying talk metadata for the talk swipe game."""
    parts = []
    for d in days:
        for talks in d["rooms_map"].values():
            for t in talks:
                color = CONF_COLOR.get(t["conf"], "#999")
                short = CONF_SHORT.get(t["conf"], t["conf"])
                card_id = t["paper"] if t["paper"] else f"PLENARY-{t['title']}"
                start_min = to_minutes(t["time_sort"])
                end_str = slot_end(t["time_slot"])
                time_str = f"{start_min // 60:02d}:{start_min % 60:02d}"
                time_label = f"{time_str}–{end_str} CEST" if end_str else time_str
                parts.append(
                    f'<span class="talk-swipe-card-data" '
                    f'data-id="{e(card_id)}" '
                    f'data-day="{e(d["date_iso"])}" '
                    f'data-conf="{e(t["conf"])}" '
                    f'data-title="{e(t["title"])}" '
                    f'data-paper="{e(t["paper"])}" '
                    f'data-author="{e(t["author"])}" '
                    f'data-abstract="{e(t["abstract"] or "")}" '
                    f'data-url="{e(t["url"] or "")}" '
                    f'data-color="{color}" '
                    f'data-short="{e(short)}" '
                    f'data-time="{e(time_label)}" '
                    f'data-room="{e(t["room"])}"></span>'
                )
    return '<div id="talk-swipe-data" style="display:none">' + "".join(parts) + "</div>"


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
        f'<button class="swipe-action-btn undo-btn" onclick="undoTalkSwipe()">&#8630;</button>'
        f'<button class="swipe-action-btn save-btn" onclick="applyTalkSwipeAction(\'save\')">&#9733;</button>'
        f"</div>"
        f'<div class="swipe-keys">&#8592; skip &nbsp;|&nbsp; &#8594; save &nbsp;|&nbsp; &#8593; undo</div>'
    )


def render_talk_list_page(days: list[dict]) -> str:
    """Flat chronological talk list, similar in layout to the poster page."""
    day_items: dict[str, list[str]] = {}
    all_items: list[str] = []

    for d in days:
        all_talks: list[dict] = []
        for talks in d["rooms_map"].values():
            all_talks.extend(talks)
        all_talks.sort(
            key=lambda t: (to_minutes(t["time_sort"]), t["room"], t["title"])
        )

        items: list[str] = []
        for talk in all_talks:
            color = CONF_COLOR.get(talk["conf"], "#999")
            short = CONF_SHORT.get(talk["conf"], talk["conf"])
            search_str = e(
                f"{talk['title']} {talk['paper']} {talk['author']} {talk['abstract']}"
            )
            href = f"https://spie.org{talk['url']}" if talk.get("url") else ""
            card_id = e(talk["paper"] if talk["paper"] else f"PLENARY-{talk['title']}")
            start_min = to_minutes(talk["time_sort"])
            time_str = f"{start_min // 60:02d}:{start_min % 60:02d}"
            end_str = slot_end(talk["time_slot"])
            time_label = f"{time_str}–{end_str}" if end_str else time_str
            title_html = f'<span class="talk-link" onclick="openTalkModal(this)">{e(talk["title"])}</span>'
            meta = (
                f"[{e(talk['paper'])}] {e(talk['author'])}"
                if talk["conf"] != "PLENARY"
                else ""
            )
            item = (
                f'<div class="talk-list-item" data-search="{search_str}" data-id="{card_id}" '
                f"{_modal_data(talk, href, short, color)}>"
                f'<div class="talk-list-time">{time_label}<br>{e(talk["room"])}</div>'
                f'<div class="talk-list-body">'
                f'<span class="talk-list-conf" style="color:{color}">{e(short)}</span>'
                f'<div class="talk-list-title">{title_html}</div>'
                f"{'<div class="talk-list-meta">' + meta + '</div>' if meta else ''}"
                f"</div>"
                f'<button class="talk-skip-btn" onclick="toggleTalkSkip(this)" title="Not interested">&#10005;</button>'
                f'<button class="star-btn" onclick="toggleBookmark(this)" '
                f'title="Save to My Schedule">&#9734;</button>'
                f"</div>"
            )
            items.append(item)
            all_items.append(item)

        day_items[d["date_iso"]] = items

    tabs = (
        '<button class="tab-btn active" data-day="all" '
        'onclick="switchTalkListDay(\'all\')" style="font-size:12px;padding:5px 14px">'
        "All days</button>"
    )
    tabs += "".join(
        f'<button class="tab-btn" data-day="{d["date_iso"]}" '
        f"onclick=\"switchTalkListDay('{d['date_iso']}')\" "
        f'style="font-size:12px;padding:5px 14px">{e(d["label"])}</button>'
        for d in days
    )

    all_panel = (
        '<div class="talk-list-day-panel active" id="talklist-day-all">'
        + "".join(all_items)
        + "</div>"
    )
    day_panels = "".join(
        f'<div class="talk-list-day-panel" id="talklist-day-{d["date_iso"]}">'
        + "".join(day_items[d["date_iso"]])
        + "</div>"
        for d in days
    )

    return f'<div class="tabs">{tabs}</div>' + all_panel + day_panels


def build_html(days: list[dict], poster_days: list[dict]) -> str:
    legend = "".join(
        f'<span class="legend-item" data-conf="{e(c)}" onclick="toggleConfFilter(\'{e(c)}\')">'
        f'<span class="legend-dot" style="background:{CONF_COLOR.get(c, "#999")}"></span>'
        f"{e(CONF_SHORT.get(c, c))}</span>"
        for c in sorted(CONF_SHORT)
    )

    view_nav = (
        '<nav class="view-nav">'
        '<button class="view-btn active" data-view="schedule" onclick="switchView(\'schedule\')">Talk Schedule</button>'
        '<button class="view-btn" data-view="talklist" onclick="switchView(\'talklist\')">Talk List</button>'
        f'<button class="view-btn" data-view="talkswipe" onclick="switchView(\'talkswipe\')">{TINDER_SVG}Talk Swipe</button>'
        '<span class="view-nav-divider"></span>'
        '<button class="view-btn" data-view="posters" onclick="switchView(\'posters\')">Poster List</button>'
        f'<button class="view-btn" data-view="swipe" onclick="switchView(\'swipe\')">{TINDER_SVG}Poster Swipe</button>'
        "</nav>"
    )

    tabs = "".join(
        f'<button class="tab-btn{" active" if i == 0 else ""}" '
        f'data-day="{d["date_iso"]}" onclick="switchDay(\'{d["date_iso"]}\')">'
        f"{e(d['label'])}</button>"
        for i, d in enumerate(days)
    )

    schedule_panels = "".join(
        f'<div class="day-panel" id="day-{d["date_iso"]}" '
        f'style="display:{"block" if i == 0 else "none"}">'
        f"{render_calendar_day(d)}</div>"
        for i, d in enumerate(days)
    )

    talklist_html = render_talk_list_page(days)
    talkswipe_html = render_talk_swipe_page(days)
    talk_swipe_data = render_talk_swipe_data(days)
    poster_html = render_poster_page(poster_days)
    swipe_html = render_swipe_page(poster_days)
    swipe_data = render_swipe_data(poster_days)

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
  <button id="share-btn" onclick="openShareModal()">&#8645; Export / Import</button>
  <span id="match-count"></span>
  <a href="https://github.com/ppp-one/spie-astronomy-schedule" target="_blank" rel="noopener" class="github-link" title="View on GitHub" style="margin-left:auto;color:#7eb8f7;display:flex;align-items:center;text-decoration:none;">
    <svg height="20" width="20" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
  </a>
</div>

<div class="legend">{legend}</div>
{view_nav}
<div class="page active" id="page-schedule">
<div id="schedule-body">
<div class="tabs">{tabs}</div>
{schedule_panels}
</div>
</div>
<div class="page" id="page-talklist">
<div id="talklist-body">
{talklist_html}
</div>
</div>
<div class="page" id="page-posters">
<div id="poster-body">
{poster_html}
</div>
</div>
<div class="page" id="page-talkswipe">
<div id="talkswipe-body">
{talkswipe_html}
</div>
</div>
{talk_swipe_data}
<div class="page" id="page-swipe">
<div id="swipe-body">
{swipe_html}
</div>
</div>
{swipe_data}

<div class="modal-backdrop" id="share-modal">
  <div class="modal">
    <h2>&#8645; Export / Import bookmarks</h2>
    <p>Copy the list below and paste it on another device to transfer your saved talks.</p>
    <label style="font-size:11px;font-weight:600;color:#555">Your code</label>
    <textarea id="export-code" readonly placeholder="(no bookmarks saved yet)"></textarea>
    <div class="modal-row">
      <button class="modal-btn primary" onclick="copyExport()">Copy to clipboard</button>
      <button class="modal-btn danger" onclick="clearAllBookmarks()">Clear all</button>
      <button class="modal-btn secondary" onclick="closeShareModal()">Close</button>
    </div>
    <p style="margin-top:16px;margin-bottom:4px">Paste a list from another device:</p>
    <textarea id="import-code" placeholder="Paste list here…"></textarea>
    <div class="modal-row">
      <button class="modal-btn primary" onclick="importBookmarks()">Import</button>
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
    days = build_days(records)
    poster_days = build_poster_days(records)
    html = build_html(days, poster_days)
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
