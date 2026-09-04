#!/usr/bin/env python3
"""
Redump.org Batch Disc Importer for DEMOSCENE.
Discovers and imports PlayStation 1, 2, and 3 demo discs, coverdiscs, and promos
directly from Redump into the DEMOSCENE master SQLite catalog.

Usage:
  python scripts/redump_importer.py --system ps2 --region Eu --category demos
  python scripts/redump_importer.py --system ps1 --region Eu --category coverdiscs
  python scripts/redump_importer.py --system ps3 --region Eu --category promos
  python scripts/redump_importer.py --dry-run
"""
import argparse
import re
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Set

import json
from app.core.config import settings
from app.core import database as db

REDUMP_BASE = "http://redump.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DEMOSCENE/2.0 (PlayStation Demo Collector)"
}

SYSTEM_URL_MAP = {
    "ps1": "psx",
    "psx": "psx",
    "ps2": "ps2",
    "ps3": "ps3"
}

CONSOLE_NAME_MAP = {
    "psx": "PS1",
    "ps1": "PS1",
    "ps2": "PS2",
    "ps3": "PS3"
}


def get_existing_catalog_keys(db_path: str = None) -> Dict[str, Set[str]]:
    """Retrieve all existing SCED serials, titles, and redump IDs from database."""
    conn = db.get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, title, catalog_line, sced_codes_json, redump_id FROM demos")
    rows = cur.fetchall()
    conn.close()

    serials = set()
    titles = set()
    redump_ids = set()

    for r in rows:
        titles.add(r["title"].lower().strip())
        if r["catalog_line"]:
            serials.add(r["catalog_line"].upper().strip())
        if r["redump_id"]:
            redump_ids.add(r["redump_id"])
        sceds = json.loads(r["sced_codes_json"] or "[]")
        for s in sceds:
            serials.add(s.upper().strip())

    return {
        "serials": serials,
        "titles": titles,
        "redump_ids": redump_ids
    }


def fetch_redump_category_page(system_code: str, category: str, region: str = "Eu", page: int = 1) -> List[Dict[str, Any]]:
    """Fetch and parse one page of discs from Redump category view."""
    reg_slug = f"region/{region}/" if region and region.lower() != "all" else ""
    url = f"{REDUMP_BASE}/discs/system/{system_code}/{reg_slug}category/{category}/"
    if page > 1:
        url += f"?page={page}"

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        entries = []
        rows = table.find_all("tr")[1:]  # skip header
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 7:
                continue

            # Title extraction with subtitle stripping
            td_title = tds[1]
            link = td_title.find("a")
            href = link.get("href", "") if link else ""
            disc_id_match = re.search(r"/disc/(\d+)/", href)
            disc_id = int(disc_id_match.group(1)) if disc_id_match else None

            if link:
                span_sub = link.find("span", class_="small")
                subtitle = span_sub.get_text(strip=True) if span_sub else ""
                if span_sub:
                    span_sub.decompose()
                clean_title = link.get_text(" ", strip=True)
            else:
                clean_title = td_title.get_text(" ", strip=True)

            # Columns: [Region, Title, System, Version, Edition, Languages, Serial, Status]
            version = tds[3].get_text(strip=True)
            edition = tds[4].get_text(strip=True)
            languages = tds[5].get_text(strip=True)
            serial = tds[6].get_text(strip=True).upper().replace("\xa0", " ").strip()

            entries.append({
                "redump_id": disc_id,
                "title": clean_title,
                "serial": serial,
                "version": version,
                "edition": edition,
                "languages": languages,
                "category": category,
                "redump_url": f"{REDUMP_BASE}/disc/{disc_id}/" if disc_id else url
            })

        return entries
    except Exception as e:
        print(f"  ⚠️ Error fetching {url}: {e}")
        return []


def parse_playable_game_heuristic(title: str, category: str) -> List[str]:
    """Extract game name if this is a standalone demo or single-game release."""
    lower_title = title.lower()
    # Check if multi-game magazine compilation
    is_compilation = any(k in lower_title for k in ("magazine", "euro demo", "bonus demo", "sampler", "station", "issue", "vol.", "volume"))
    if is_compilation:
        return []

    # Clean out demo suffixes
    clean = re.sub(r"(?i)\s+(?:demo|special edition demo|taikenban|preview disc|trial version|playable demo)\b.*$", "", title).strip()
    return [clean] if clean else [title]


def run_batch_import(
    systems: List[str],
    categories: List[str],
    region: str = "Eu",
    max_pages_per_cat: int = 5,
    dry_run: bool = False,
    db_path: str = None
) -> Dict[str, Any]:
    """Execute batch crawl and ingestion across specified systems and categories."""
    existing = get_existing_catalog_keys(db_path)
    total_found = 0
    total_skipped = 0
    total_added = 0
    added_records = []

    print(f"\n========================================================")
    print(f"💿 DEMOSCENE Redump Ingestion Engine")
    print(f"Systems: {', '.join(systems).upper()} | Region: {region} | Categories: {', '.join(categories)}")
    print(f"Mode: {'DRY RUN (Preview Only)' if dry_run else 'ACTIVE COMMIT'}")
    print(f"Existing known discs in database: {len(existing['titles'])}")
    print(f"========================================================\n")

    for sys_arg in systems:
        sys_code = SYSTEM_URL_MAP.get(sys_arg.lower(), "ps2")
        console_name = CONSOLE_NAME_MAP.get(sys_code, "PS2")

        for cat in categories:
            print(f"🔍 Crawling [{console_name}] Category: '{cat}' (Region: {region})...")
            for page in range(1, max_pages_per_cat + 1):
                entries = fetch_redump_category_page(sys_code, cat, region=region, page=page)
                if not entries:
                    break

                for item in entries:
                    total_found += 1
                    title = item["title"]
                    serial = item["serial"]
                    r_id = item["redump_id"]

                    # Check duplicates
                    is_dupe = False
                    if r_id and r_id in existing["redump_ids"]:
                        is_dupe = True
                    elif serial and serial in existing["serials"]:
                        is_dupe = True
                    elif title.lower() in existing["titles"]:
                        is_dupe = True

                    if is_dupe:
                        total_skipped += 1
                        continue

                    # New disc to import!
                    playables = parse_playable_game_heuristic(title, cat)
                    section_name = f"Redump {cat.capitalize()}"
                    country = "Europe" if region.lower() == "eu" else ("North America" if region.lower() == "am" else "Worldwide")

                    record_data = {
                        "title": title,
                        "console": console_name,
                        "section_name": section_name,
                        "section_group": "Redump Preservation",
                        "section_url": item["redump_url"],
                        "sced_codes": [serial] if serial else [],
                        "country": country,
                        "categories": {"Playable": playables} if playables else {},
                        "notes": f"Imported from Redump.org (ID: {r_id or 'N/A'}, Category: {cat})",
                        "source": "redump",
                        "redump_id": r_id,
                        "primary_thumbnail": f"/assets/demopals/placeholder_{console_name.lower()}.png"
                    }

                    if not dry_run:
                        created = db.create_manual_demo(record_data, db_path=db_path)
                        added_records.append(created)
                        # Update running in-memory tracking
                        if serial: existing["serials"].add(serial)
                        if r_id: existing["redump_ids"].add(r_id)
                        existing["titles"].add(title.lower())
                    else:
                        added_records.append(record_data)

                    total_added += 1
                    status_str = f"[ADDED] {console_name} | {title} | {serial or 'NO-SERIAL'} | Games: {playables or '[Multi-game / Pending]'}"
                    print(f"  + {status_str}")

                time.sleep(0.5)  # Be polite to Redump servers

    print(f"\n========================================================")
    print(f"📊 INGESTION SUMMARY")
    print(f"Total Discs Inspected: {total_found}")
    print(f"Already in Catalog (Skipped): {total_skipped}")
    print(f"Newly Added Discs: {total_added}")
    print(f"========================================================\n")

    return {
        "total_inspected": total_found,
        "already_cataloged": total_skipped,
        "newly_added": total_added,
        "records": added_records
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch import demo discs from Redump.org into DEMOSCENE.")
    parser.add_argument("--system", choices=["ps1", "ps2", "ps3", "all"], default="ps2", help="Target console")
    parser.add_argument("--category", choices=["demos", "coverdiscs", "promos", "all"], default="all", help="Target category")
    parser.add_argument("--region", default="Eu", help="Redump region code: Eu (Europe), Am (USA), As (Asia), all")
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages to crawl per category")
    parser.add_argument("--dry-run", action="store_true", help="Preview matches without inserting into database")

    args = parser.parse_args()

    systems = ["ps1", "ps2", "ps3"] if args.system == "all" else [args.system]
    categories = ["demos", "coverdiscs"] if args.category == "all" else [args.category]
    if "ps3" in systems and args.category in ("all", "promos"):
        categories.append("promos")

    run_batch_import(
        systems=systems,
        categories=categories,
        region=args.region,
        max_pages_per_cat=args.max_pages,
        dry_run=args.dry_run
    )
