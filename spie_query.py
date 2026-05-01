#!/usr/bin/env python3

import json
import time
from pathlib import Path

import requests

BASE_URL = "https://spie.org/search/GetSearchResults"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:147.0) Gecko/20100101 Firefox/147.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "DNT": "1",
    "Sec-GPC": "1",
    "Referer": (
        "https://spie.org/conferences-and-exhibitions/"
        "astronomical-telescopes-and-instrumentation/"
        "program/browse-program"
    ),
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

# Paste your cookies here if needed
COOKIES = {}


PARAMS_TEMPLATE = {
    "searchterm": "",
    "searchtype": "browseProgram",
    "exhibitioncode": "AS26",
}

PAGE_SIZE = 50
OUTPUT_DIR = Path("spie_query_results")
OUTPUT_DIR.mkdir(exist_ok=True)


def build_query(page: int) -> str:
    return f"term=&pageSize={PAGE_SIZE}&page={page}&sortBy=DateAsc&tab=Presentation"


def fetch_page(session: requests.Session, page: int):
    params = PARAMS_TEMPLATE.copy()
    params["query"] = build_query(page)

    response = session.get(
        BASE_URL,
        headers=HEADERS,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    try:
        return response.json()
    except Exception:
        print(f"[!] Failed to parse JSON on page {page}")
        print(response.text[:1000])
        raise


def is_empty_result(data) -> bool:
    if data is None:
        return True

    # Common patterns
    if isinstance(data, list):
        return len(data) == 0

    if isinstance(data, dict):
        for key in ["results", "items", "data", "presentations"]:
            if key in data and isinstance(data[key], list):
                return len(data[key]) == 0

        # Fallback: empty dict
        return len(data) == 0

    return False


def main():
    session = requests.Session()

    if COOKIES:
        session.cookies.update(COOKIES)

    page = 11

    while True:
        print(f"[*] Fetching page {page}")

        try:
            data = fetch_page(session, page)
        except Exception as e:
            print(f"[!] Error on page {page}: {e}")
            break

        if is_empty_result(data):
            print("[*] No more results")
            break

        output_file = OUTPUT_DIR / f"page_{page:03d}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[+] Saved {output_file}")

        page += 1

        # Be polite
        time.sleep(3)


if __name__ == "__main__":
    main()
