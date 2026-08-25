"""
PlayStation Demo Pals Scraper
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

import db

BASE_URL = "https://crimson-ceremony.net/demopals/"
SCED_PATTERN = re.compile(
    r"(?:SCED|SCES|SLED|SLES|PBPX|PAPX|SCDX|SLUS|SCUS|SLES|PSXC|SLKA|SLPM)-\d+[A-Za-z0-9#]*",
    re.IGNORECASE
)

# Known sections configuration if discovery needs fallback
SECTION_CONFIG = [
    # PS1
    {"console": "PS1", "group": "OPM demos", "name": "Euro Demo", "path": "eurodemo/index.php"},
    {"console": "PS1", "group": "OPM demos", "name": "France", "path": "eurofrance/index.php"},
    {"console": "PS1", "group": "OPM demos", "name": "Germany", "path": "eurogermany/index.php"},
    {"console": "PS1", "group": "OPM specials", "name": "Europe", "path": "opmspecials/index.php"},
    {"console": "PS1", "group": "OPM specials", "name": "Germany", "path": "sonderheft/index.php"},
    {"console": "PS1", "group": "OPM specials", "name": "Essential Playstation", "path": "essential/index.php"},
    {"console": "PS1", "group": "Other series", "name": "Demo One", "path": "demo1/index.php"},
    {"console": "PS1", "group": "Other series", "name": "Next", "path": "next/index.php"},
    {"console": "PS1", "group": "Other series", "name": "Play Fun", "path": "playfun/index.php"},
    {"console": "PS1", "group": "Other series", "name": "PlayStation Zone", "path": "playzone/index.php"},
    {"console": "PS1", "group": "Other series", "name": "Registered Users Demo", "path": "registered/index.php"},
    {"console": "PS1", "group": "Other series", "name": "Station", "path": "station/index.php"},
    {"console": "PS1", "group": "The rest", "name": "Other samplers", "path": "samplers/index.php"},
    {"console": "PS1", "group": "The rest", "name": "Dedicated demos", "path": "dedicated/index.php"},
    # PS2
    {"console": "PS2", "group": "OPS2M demos", "name": "Europe", "path": "ops2meur/index.php"},
    {"console": "PS2", "group": "OPS2M demos", "name": "Germany", "path": "ops2mger/index.php"},
    {"console": "PS2", "group": "OPS2M specials", "name": "Europe", "path": "ops2meurspecials/index.php"},
    {"console": "PS2", "group": "OPS2M specials", "name": "Germany", "path": "ops2mgerspecials/index.php"},
    {"console": "PS2", "group": "OPS2M specials", "name": "UK", "path": "ops2mukspecials/index.php"},
]


def discover_sections(session: requests.Session) -> List[Dict[str, Any]]:
    """Discover all sections dynamically from navigation or fallback to config."""
    try:
        resp = session.get(BASE_URL, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        nav = soup.find("nav")
        if not nav:
            return [{**s, "url": urljoin(BASE_URL, s["path"])} for s in SECTION_CONFIG]

        sections = []
        current_group = "General"
        for child in nav.find_all(["dt", "dd"]):
            if child.name == "dt":
                current_group = child.text.strip()
            elif child.name == "dd":
                a = child.find("a")
                if a and a.get("href") and "master" not in a["href"]:
                    url = urljoin(BASE_URL, a["href"])
                    name = a.text.strip()
                    console = "PS2" if "ops2m" in url or "OPS2M" in current_group else "PS1"
                    sections.append({
                        "console": console,
                        "group": current_group,
                        "name": name,
                        "url": url
                    })
        return sections if sections else [{**s, "url": urljoin(BASE_URL, s["path"])} for s in SECTION_CONFIG]
    except Exception as e:
        print(f"Discovery notice: {e}, using default section list.")
        return [{**s, "url": urljoin(BASE_URL, s["path"])} for s in SECTION_CONFIG]


def generate_scan_urls(base_url: str, img_key: str, max_scans: int = 6) -> List[str]:
    """
    Generate likely scan URLs for a given img_key (e.g., fra001-1.jpg, fra001-2.jpg).
    """
    if not img_key:
        return []
    # If base_url is https://crimson-ceremony.net/demopals/ops2meur/index.php
    # img folder is https://crimson-ceremony.net/demopals/ops2meur/
    folder_url = base_url.rsplit("/", 1)[0] + "/"
    # Scan images start at index 1 (index 0 is thumbnail)
    return [f"{folder_url}{img_key}-{i}.jpg" for i in range(1, max_scans + 1)]


def parse_section_page(html_content: bytes, section_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse all demo disc entries on a single section page."""
    soup = BeautifulSoup(html_content, "html.parser")
    section = soup.find("section")
    if not section:
        return []

    entries = []
    h2_elements = section.find_all("h2", recursive=False)
    section_url = section_meta["url"]
    console = section_meta["console"]
    group = section_meta["group"]
    section_name = section_meta["name"]
    section_slug = re.sub(r"[^a-z0-9]+", "_", f"{console}_{section_name}".lower()).strip("_")

    for idx, h2 in enumerate(h2_elements):
        title = h2.get_text(strip=True)
        h2_id = h2.get("id", "")

        # Look for sibling <h3> containing catalog line (e.g. SCED-50065 9246725)
        sibling = h2.find_next_sibling()
        catalog_line = ""
        if sibling and sibling.name == "h3":
            catalog_line = sibling.get_text(strip=True)
            sibling = sibling.find_next_sibling()

        # Find all SCED/SLES/PBPX codes
        sced_codes = list(dict.fromkeys(SCED_PATTERN.findall(f"{h2_id} {catalog_line} {title}")))

        # Create a unique ID
        clean_title_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        primary_code = sced_codes[0] if sced_codes else (h2_id if h2_id else f"demo-{idx+1}")
        demo_id = f"{section_slug}__{clean_title_slug}__{primary_code}".lower()

        categories = {}
        variants = []
        notes = ""

        # Parse <div class="demo">
        if sibling and sibling.name == "div" and "demo" in sibling.get("class", []):
            demo_div = sibling
            
            # Contents list <dl class="contents">
            dl = demo_div.find("dl", class_="contents")
            if dl:
                curr_cat = "General"
                for el in dl.children:
                    if el.name == "dt":
                        curr_cat = el.get_text(strip=True)
                    elif el.name == "dd":
                        text = el.get_text(strip=True)
                        if not text:
                            continue
                        if curr_cat == "Notes":
                            notes = f"{notes} {text}".strip()
                        else:
                            norm_cat = "Screenshots" if curr_cat == "Sreenshots" else curr_cat
                            categories.setdefault(norm_cat, []).append(text)

            # Variations list <div class="variations">
            v_div = demo_div.find("div", class_="variations")
            if v_div:
                for ul in v_div.find_all("ul", class_="varitem"):
                    thumb_li = ul.find("li", class_="vardisc")
                    flag_li = ul.find("li", class_="varflag")
                    title_li = ul.find("li", class_="vartitle")

                    thumb_url = None
                    img_key = None
                    if thumb_li:
                        img = thumb_li.find("img")
                        if img and img.get("src"):
                            thumb_url = urljoin(section_url, img["src"])
                        a = thumb_li.find("a")
                        if a and a.get("href") and "img=" in a["href"]:
                            img_key = a["href"].split("img=")[1].split("#")[0]

                    country = "Europe"
                    flag_url = None
                    if flag_li:
                        img = flag_li.find("img")
                        if img:
                            country = img.get("title") or img.get("alt") or "Europe"
                            if img.get("src"):
                                flag_url = urljoin(BASE_URL, img["src"])

                    disc_title = title_li.get_text(" ", strip=True) if title_li else title

                    # Extract SCED in variant title if any
                    v_sceds = SCED_PATTERN.findall(disc_title)
                    variant_sced = v_sceds[0] if v_sceds else None

                    var_id = img_key if img_key else re.sub(r"[^a-z0-9]+", "_", f"{country}_{disc_title}".lower())[:30]

                    variants.append({
                        "variant_id": var_id,
                        "disc_title": disc_title,
                        "thumbnail": thumb_url,
                        "img_key": img_key,
                        "country": country,
                        "flag_icon": flag_url,
                        "sced_override": variant_sced,
                        "scan_previews": generate_scan_urls(section_url, img_key) if img_key else []
                    })

        # Determine primary high-resolution thumbnail (prefer Slipcase / Cover Front -1.jpg)
        primary_thumbnail = None
        for v in variants:
            if v.get("img_key"):
                folder_url = section_url.rsplit("/", 1)[0] + "/"
                primary_thumbnail = f"{folder_url}{v['img_key']}-1.jpg"
                break
        if not primary_thumbnail:
            for v in variants:
                if v.get("thumbnail") and "noimg.jpg" not in v["thumbnail"]:
                    primary_thumbnail = v["thumbnail"]
                    break
        if not primary_thumbnail and variants:
            primary_thumbnail = variants[0].get("thumbnail")

        entries.append({
            "id": demo_id,
            "console": console,
            "section_group": group,
            "section_name": section_name,
            "section_url": section_url,
            "title": title,
            "catalog_line": catalog_line,
            "sced_codes": sced_codes,
            "notes": notes,
            "categories": categories,
            "variants": variants,
            "primary_thumbnail": primary_thumbnail
        })

    return entries


def run_scraper(db_path: str = db.DB_PATH, json_output_path: str = "demos.json", verbose: bool = True) -> Dict[str, Any]:
    """
    Run full scrape across all sections, saving to SQLite and JSON.
    """
    start_time = time.time()
    db.init_db(db_path)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PlayStation Demo Scene Collector/1.0"
    })

    if verbose:
        print("🔍 Discovering sections from crimson-ceremony.net/demopals...")

    sections = discover_sections(session)
    if verbose:
        print(f"📋 Found {len(sections)} sections to scrape.")

    all_demos = []
    section_stats = []

    for idx, s in enumerate(sections, 1):
        try:
            if verbose:
                print(f"[{idx}/{len(sections)}] Scraping [{s['console']}] {s['name']} ({s['url']})...", end="", flush=True)
            
            resp = session.get(s["url"], timeout=15)
            resp.raise_for_status()
            
            entries = parse_section_page(resp.content, s)
            all_demos.extend(entries)
            
            section_stats.append({
                "console": s["console"],
                "section": s["name"],
                "count": len(entries)
            })
            if verbose:
                print(f" ✅ {len(entries)} demos")
        except Exception as e:
            if verbose:
                print(f" ❌ Error: {e}")

    # Save to SQLite
    if verbose:
        print(f"\n💾 Saving {len(all_demos)} demos to database ({db_path})...")
    db.save_demos_bulk(all_demos, db_path)

    # Save JSON backup / export
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump({
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_demos": len(all_demos),
            "demos": all_demos
        }, f, indent=2, ensure_ascii=False)

    elapsed = round(time.time() - start_time, 2)
    summary = {
        "success": True,
        "total_demos": len(all_demos),
        "total_sections": len(sections),
        "elapsed_seconds": elapsed,
        "section_stats": section_stats
    }

    if verbose:
        print(f"✨ Scrape finished in {elapsed}s! Total demos scraped: {len(all_demos)}")
        print(f"📁 Database: {db_path}")
        print(f"📁 JSON File: {json_output_path}\n")

    return summary


if __name__ == "__main__":
    run_scraper()
