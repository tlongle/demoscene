"""
PlayStation Demo Pals Scraper.
Scrapes demo discs, games, categories, variants, and high-res scans
from https://crimson-ceremony.net/demopals into SQLite & JSON.
"""
import requests
from bs4 import BeautifulSoup
import re
import os
import json
import time
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.database import save_demos_bulk, get_stats
from app.services.parser import parse_block, SCED_PATTERN

BASE_URL = "https://crimson-ceremony.net/demopals/"

# Known sections configuration if discovery needs fallback
SECTION_CONFIG = [
    # PS1
    {"console": "PS1", "group": "OPM demos", "name": "Euro Demo", "path": "eurodemo/index.php"},
    {"console": "PS1", "group": "OPM demos", "name": "France", "path": "eurofrance/index.php"},
    {"console": "PS1", "group": "OPM demos", "name": "Germany", "path": "eurogermany/index.php"},
    {"console": "PS1", "group": "OPM specials", "name": "Europe", "path": "opmspecials/index.php"},
    {"console": "PS1", "group": "OPM specials", "name": "Germany", "path": "sonderheft/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "Essential Playstation", "path": "essential/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "Demo One", "path": "demo1/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "Next", "path": "next/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "Play Fun", "path": "playfun/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "PlayStation Zone", "path": "playzone/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "Registered Users Demo", "path": "registered/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "Station", "path": "station/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "Other samplers", "path": "samplers/index.php"},
    {"console": "PS1", "group": "General samplers", "name": "Dedicated demos", "path": "dedicated/index.php"},
    # PS2
    {"console": "PS2", "group": "OPS2M demos", "name": "Europe", "path": "ops2meur/index.php"},
    {"console": "PS2", "group": "OPS2M demos", "name": "Germany", "path": "ops2mger/index.php"},
    {"console": "PS2", "group": "OPS2M specials", "name": "Europe", "path": "ops2meurspecials/index.php"},
    {"console": "PS2", "group": "OPS2M specials", "name": "Germany", "path": "ops2mgerspecials/index.php"},
    {"console": "PS2", "group": "OPS2M specials", "name": "UK", "path": "ops2mukspecials/index.php"},
]

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PlayStationDemoCollector/2.0"
})


def make_demo_id(console: str, section_name: str, title: str, sced_or_catalog: str) -> str:
    """Generate a clean, deterministic unique ID for a demo disc."""
    clean_section = re.sub(r"[^\w\-]", "_", section_name.strip().lower())
    clean_title = re.sub(r"[^\w\-]", "-", title.strip().lower())
    clean_code = re.sub(r"[^\w\-]", "-", sced_or_catalog.strip().lower())
    if not clean_code:
        clean_code = "demo"
    return f"{console.lower()}_{clean_section}__{clean_title}__{clean_code}"[:120]


def scrape_section_html(section: Dict[str, Any], verbose: bool = False) -> List[Dict[str, Any]]:
    """Scrape a single section index page from Crimson Ceremony."""
    section_url = urljoin(BASE_URL, section["path"])
    try:
        res = SESSION.get(section_url, timeout=20)
        res.raise_for_status()
    except Exception as e:
        if verbose:
            print(f"❌ Failed to fetch section: {section_url} -> {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    entries = []

    # Strategy 1: Look for table rows with demo blocks
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            tds = row.find_all("td")
            if not tds:
                continue

            text_content = row.get_text("\n", strip=True)
            if not text_content or len(text_content) < 5:
                continue

            # Check if this row looks like a demo entry
            parsed = parse_block(text_content, default_console=section["console"])
            if parsed and parsed.get("title"):
                # Extract image links and flags from HTML tags
                imgs = row.find_all("img")
                img_links = row.find_all("a")

                variant_imgs = []
                for a in img_links:
                    href = a.get("href", "")
                    if href.endswith(".jpg") or href.endswith(".png"):
                        variant_imgs.append(urljoin(section_url, href))

                for img in imgs:
                    src = img.get("src", "")
                    if "f-" in src:
                        full_flag = urljoin(section_url, src)
                        if parsed["variants"]:
                            parsed["variants"][0]["flag_icon"] = full_flag

                # Attach absolute section metadata
                sced_repr = parsed["sced_codes"][0] if parsed["sced_codes"] else parsed.get("catalog_line", "")
                demo_id = make_demo_id(section["console"], section["name"], parsed["title"], sced_repr)

                # Prioritize high-res front cover (-1.jpg)
                primary_thumbnail = ""
                if parsed.get("variants") and parsed["variants"][0].get("img_key"):
                    key = parsed["variants"][0]["img_key"]
                    primary_thumbnail = urljoin(section_url, f"{key}-1.jpg")
                elif variant_imgs:
                    high_res = [img for img in variant_imgs if "-1.jpg" in img or "-2.jpg" in img]
                    primary_thumbnail = high_res[0] if high_res else variant_imgs[0]

                entry = {
                    "id": demo_id,
                    "console": section["console"],
                    "section_group": section["group"],
                    "section_name": section["name"],
                    "section_url": section_url,
                    "title": parsed["title"],
                    "catalog_line": parsed["catalog_line"],
                    "sced_codes": parsed["sced_codes"],
                    "notes": parsed["notes"],
                    "categories": parsed["categories"],
                    "variants": parsed["variants"],
                    "primary_thumbnail": primary_thumbnail
                }
                entries.append(entry)

    # Strategy 2: If table strategy yielded few results, fallback to block text splitting
    if len(entries) < 2:
        raw_text = soup.get_text("\n")
        blocks = re.split(r"\n\s*\n", raw_text)
        for b in blocks:
            b_clean = b.strip()
            if not b_clean:
                continue
            parsed = parse_block(b_clean, default_console=section["console"])
            if parsed and parsed.get("title") and (parsed.get("categories") or parsed.get("sced_codes")):
                sced_repr = parsed["sced_codes"][0] if parsed["sced_codes"] else parsed.get("catalog_line", "")
                demo_id = make_demo_id(section["console"], section["name"], parsed["title"], sced_repr)
                
                primary_thumbnail = ""
                if parsed.get("variants") and parsed["variants"][0].get("img_key"):
                    key = parsed["variants"][0]["img_key"]
                    primary_thumbnail = urljoin(section_url, f"{key}-1.jpg")

                entry = {
                    "id": demo_id,
                    "console": section["console"],
                    "section_group": section["group"],
                    "section_name": section["name"],
                    "section_url": section_url,
                    "title": parsed["title"],
                    "catalog_line": parsed["catalog_line"],
                    "sced_codes": parsed["sced_codes"],
                    "notes": parsed["notes"],
                    "categories": parsed["categories"],
                    "variants": parsed["variants"],
                    "primary_thumbnail": primary_thumbnail
                }
                entries.append(entry)

    # Deduplicate entries by ID
    unique_entries = {}
    for e in entries:
        if e["id"] not in unique_entries:
            unique_entries[e["id"]] = e

    return list(unique_entries.values())


def discover_all_sections(verbose: bool = False) -> List[Dict[str, Any]]:
    """Discover all active section links from crimson-ceremony.net/demopals."""
    try:
        res = SESSION.get(BASE_URL, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        discovered = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "index.php" in href or href.endswith("/"):
                path = href.replace(BASE_URL, "").strip("/")
                if not path.endswith(".php"):
                    path = f"{path}/index.php"

                # Check if this matches any known section config
                for s in SECTION_CONFIG:
                    if s["path"] == path or s["path"].split("/")[0] == path.split("/")[0]:
                        discovered.append({
                            "console": s["console"],
                            "group": s["group"],
                            "name": s["name"],
                            "path": s["path"]
                        })
                        break

        # Deduplicate
        seen_paths = set()
        final_sections = []
        for s in discovered:
            if s["path"] not in seen_paths:
                seen_paths.add(s["path"])
                final_sections.append(s)

        return final_sections if final_sections else SECTION_CONFIG
    except Exception as e:
        if verbose:
            print(f"⚠️ Section discovery failed ({e}). Falling back to static section config.")
        return SECTION_CONFIG


def run_scraper(db_path: str = None, verbose: bool = True) -> Dict[str, Any]:
    """Execute complete scraping run across all 19 sections and save to SQLite."""
    if verbose:
        print("\n========================================================")
        print("🔍 Starting Crimson Ceremony PS1 & PS2 Demo Scraper")
        print("========================================================\n")

    sections = discover_all_sections(verbose=verbose)
    if verbose:
        print(f"📋 Found {len(sections)} sections to scrape.")

    all_demos = []
    for idx, sec in enumerate(sections, 1):
        if verbose:
            print(f"[{idx}/{len(sections)}] Scraping [{sec['console']}] {sec['name']} ({urljoin(BASE_URL, sec['path'])})...", end=" ")
        
        demos = scrape_section_html(sec, verbose=False)
        all_demos.extend(demos)
        if verbose:
            print(f"✅ {len(demos)} demos")
        time.sleep(0.3)

    if verbose:
        print(f"\n💾 Saving {len(all_demos)} demo discs into SQLite database...")

    saved_count = save_demos_bulk(all_demos, db_path=db_path)
    stats = get_stats(db_path=db_path)
    if verbose:
        print(f"🎉 Scraping complete! Database now contains {stats['total_demos']} total discs ({stats['total_ps1']} PS1, {stats['total_ps2']} PS2).\n")

    return {
        "status": "success",
        "total_scraped": len(all_demos),
        "total_saved": saved_count,
        "stats": stats
    }
