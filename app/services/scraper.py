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
import sqlite3
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional, Tuple

from app.core.config import settings
from app.core.database import save_demos_bulk, get_stats, get_db_connection, normalize_asset_url, get_metadata, set_metadata
from app.services.parser import parse_block

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


def validate_scraped_entries(all_demos: List[Dict[str, Any]], min_expected: int = 800) -> Tuple[bool, str]:
    """
    Integrity gate: ensure scraped data is valid before allowing any database modifications.
    Rejects malformed HTML block collapses (e.g. 19 discs with 200 games each).
    """
    if not all_demos or len(all_demos) < min_expected:
        return False, f"Parsed only {len(all_demos)} demo discs (expected at least {min_expected}). Scrape rejected to prevent catalog corruption."

    # Check for anomaly: impossibly large game counts per disc (indicates table block collapse)
    for d in all_demos:
        cats = d.get("categories", {})
        total_items = sum(len(items) for items in cats.values())
        if total_items > 45:
            return False, f"Disc '{d.get('title')}' parsed with {total_items} items (max expected is 45). Scrape rejected due to DOM block corruption."

    return True, "Validation passed"


def differential_merge_demos(all_demos: List[Dict[str, Any]], db_path: str = None) -> Dict[str, Any]:
    """
    Merge scraped entries differentially:
    - Never delete or corrupt existing curated records.
    - Insert new records.
    - Fill missing SCED codes or variant scans on existing records without overwriting user data.
    - Create a pre-sync backup.
    """
    backup_dir = os.path.join(settings.DATA_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"demos_pre_sync_{timestamp}.json")

    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM demos")
    existing_rows = {r["id"]: dict(r) for r in cur.fetchall()}

    try:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(existing_rows, f, indent=2, default=str)
    except Exception as e:
        print(f"⚠️ Warning: Could not create pre-sync backup: {e}")

    inserted = 0
    updated = 0
    unchanged = 0

    for demo in all_demos:
        demo_id = demo["id"]
        contents = demo.get("categories", {})
        playable_games = contents.get("Playable", [])
        game_names_index = " | ".join(playable_games).lower()

        if demo_id not in existing_rows:
            # Genuinely new disc
            cur.execute("""
            INSERT INTO demos (
                id, console, section_group, section_name, section_url,
                title, catalog_line, sced_codes_json, notes,
                contents_json, variants_json, primary_thumbnail,
                game_names_index, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                demo["id"],
                demo["console"],
                demo["section_group"],
                demo["section_name"],
                demo["section_url"],
                demo["title"],
                demo.get("catalog_line", ""),
                json.dumps(demo.get("sced_codes", [])),
                demo.get("notes", ""),
                json.dumps(contents),
                json.dumps(demo.get("variants", [])),
                normalize_asset_url(demo.get("primary_thumbnail", "")),
                game_names_index
            ))
            inserted += 1
        else:
            # Existing disc: only update if missing sced or variant scans
            existing = existing_rows[demo_id]
            existing_sceds = json.loads(existing.get("sced_codes_json") or "[]")
            new_sceds = demo.get("sced_codes", [])
            merged_sceds = list(dict.fromkeys(existing_sceds + new_sceds))

            # Keep existing contents_json if already populated to preserve curated categories
            existing_cats = json.loads(existing.get("contents_json") or "{}")
            final_cats = existing_cats if existing_cats and any(existing_cats.values()) else contents
            final_game_idx = existing.get("game_names_index") or game_names_index

            cur.execute("""
            UPDATE demos SET
                sced_codes_json = ?,
                contents_json = ?,
                game_names_index = ?,
                primary_thumbnail = COALESCE(NULLIF(primary_thumbnail, ''), ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """, (
                json.dumps(merged_sceds),
                json.dumps(final_cats),
                final_game_idx,
                normalize_asset_url(demo.get("primary_thumbnail", "")),
                demo_id
            ))
            if merged_sceds != existing_sceds:
                updated += 1
            else:
                unchanged += 1

    conn.commit()
    conn.close()

    return {
        "total_scraped": len(all_demos),
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "backup_file": backup_file
    }


def run_scraper(db_path: str = None, verbose: bool = True) -> Dict[str, Any]:
    """Execute complete scraping run across all 19 sections with anomaly checks and differential merging."""
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

    # Validation Gate: prevent database corruption
    is_valid, reason = validate_scraped_entries(all_demos)
    if not is_valid:
        if verbose:
            print(f"\n❌ Scrape rejected by integrity gate: {reason}\n")
        return {
            "status": "error",
            "error": reason,
            "total_scraped": len(all_demos),
            "stats": get_stats(db_path=db_path)
        }

    if verbose:
        print(f"\n💾 Differentially merging {len(all_demos)} demo discs into SQLite database...")

    merge_result = differential_merge_demos(all_demos, db_path=db_path)
    stats = get_stats(db_path=db_path)

    if verbose:
        print(f"🎉 Sync complete! Inserted {merge_result['inserted']} new, updated {merge_result['updated']}. Database contains {stats['total_demos']} total discs.\n")

    return {
        "status": "success",
        "merge_result": merge_result,
        "stats": stats
    }


def peek_and_sync_updates(db_path: str = None, verbose: bool = True) -> Dict[str, Any]:
    """
    Lightweight targeted incremental update:
    1. Fetches only the Crimson Ceremony homepage updates section (1 fast GET request).
    2. Compares the newest date header against `last_synced_date` (baseline 2026.02.11).
    3. If up to date, finishes in ~200ms with zero changes to database.
    4. If newer releases are found, scrapes only those specific discs, downloads scans,
       merges them into SQLite & catalog_seed.json, and advances `last_synced_date`.
    """
    try:
        res = SESSION.get(BASE_URL, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        return {
            "status": "error",
            "error": f"Could not connect to Crimson Ceremony: {e}",
            "up_to_date": True,
            "new_discs_added": 0
        }

    last_synced_date = get_metadata("last_synced_date", "2026.02.11", db_path=db_path)
    now_ts = time.strftime("%Y-%m-%d %H:%M:%S")

    # Find update sections with date headers
    new_batches = []
    latest_found_date = last_synced_date

    for sec in soup.find_all("section"):
        h2 = sec.find("h2")
        if not h2:
            continue
        date_str = h2.get_text(strip=True)
        if not re.match(r"^\d{4}\.\d{2}\.\d{2}$", date_str):
            continue

        if date_str > latest_found_date:
            latest_found_date = date_str

        if date_str > last_synced_date:
            batch_items = []
            for ul in sec.find_all("ul", class_="varitem"):
                a = ul.find("a", href=True)
                href = a["href"] if a else ""
                img = ul.find("img", src=True)
                img_src = img["src"] if img else ""
                flag_img = ul.find("li", class_="varflag")
                flag = flag_img.find("img")["src"] if flag_img and flag_img.find("img") else ""
                title_el = ul.find("li", class_="vartitle")
                title_text = title_el.get_text("\n", strip=True) if title_el else ""
                lines = [l.strip() for l in title_text.split("\n") if l.strip()]

                disc_title = lines[0] if lines else "New Demo Disc"
                sced = lines[1] if len(lines) > 1 else ""

                batch_items.append({
                    "date": date_str,
                    "href": href,
                    "thumb_url": urljoin(BASE_URL, img_src),
                    "flag_url": urljoin(BASE_URL, flag),
                    "title": disc_title,
                    "sced": sced
                })
            if batch_items:
                new_batches.append({"date": date_str, "items": batch_items})

    set_metadata("last_check_timestamp", now_ts, db_path=db_path)

    if not new_batches:
        msg = f"Catalog is completely up to date (last remote update: {last_synced_date}). Checked at {now_ts}."
        if verbose:
            print(f"✓ {msg}")
        return {
            "status": "up_to_date",
            "message": msg,
            "last_synced_date": last_synced_date,
            "last_check_timestamp": now_ts,
            "new_discs_added": 0
        }

    # If new batches exist, scrape only the relevant sections to resolve full disc metadata
    sections_to_scrape = set()
    for batch in new_batches:
        for it in batch["items"]:
            href = it.get("href", "")
            if href:
                path_part = href.split("#")[0].strip("/")
                if "demopals/" in path_part:
                    path_part = path_part.split("demopals/", 1)[1]
                sections_to_scrape.add(path_part)

    if verbose:
        print(f"🔍 Found new releases after {last_synced_date}! Scraping {len(sections_to_scrape)} updated section(s)...")

    new_discovered_demos = []
    all_sections = discover_all_sections(verbose=False)
    for sec in all_sections:
        if sec["path"] in sections_to_scrape or any(p in sec["path"] for p in sections_to_scrape):
            demos = scrape_section_html(sec, verbose=False)
            new_discovered_demos.extend(demos)

    # Differential merge into database
    merge_result = differential_merge_demos(new_discovered_demos, db_path=db_path)
    set_metadata("last_synced_date", latest_found_date, db_path=db_path)

    # Sync into catalog_seed.json if new items were inserted
    if merge_result.get("inserted", 0) > 0:
        try:
            conn = get_db_connection(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, console, section_group, section_name, section_url, title, catalog_line, sced_codes_json, notes, contents_json, variants_json, primary_thumbnail, game_names_index FROM demos ORDER BY console, section_name, title")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()

            seed_path = os.path.join(settings.DATA_DIR, "catalog_seed.json")
            with open(seed_path, "w", encoding="utf-8") as f:
                json.dump([{
                    "id": r["id"],
                    "console": r["console"],
                    "section_group": r["section_group"],
                    "section_name": r["section_name"],
                    "section_url": r["section_url"],
                    "title": r["title"],
                    "catalog_line": r["catalog_line"],
                    "sced_codes": json.loads(r["sced_codes_json"] or "[]"),
                    "notes": r["notes"],
                    "categories": json.loads(r["contents_json"] or "{}"),
                    "variants": json.loads(r["variants_json"] or "[]"),
                    "primary_thumbnail": r["primary_thumbnail"],
                    "game_names_index": r["game_names_index"]
                } for r in rows], f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Warning: Could not update catalog_seed.json: {e}")

    msg = f"Discovered and imported {merge_result.get('inserted', 0)} new discs from {latest_found_date} release."
    if verbose:
        print(f"🎉 {msg}")

    return {
        "status": "updated",
        "message": msg,
        "last_synced_date": latest_found_date,
        "last_check_timestamp": now_ts,
        "new_discs_added": merge_result.get("inserted", 0),
        "merge_result": merge_result
    }
