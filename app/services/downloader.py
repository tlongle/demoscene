"""
Crimson Ceremony Asset Downloader & Offline Cache Pipeline.
Downloads all disc scans, slipcases, inlays, and variant covers locally into data/assets/demopals.
"""
import os
import re
import json
import time
import requests
from urllib.parse import urlparse, urljoin
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.core.database import get_db_connection

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PlayStationDemoCollector/2.0"
})


def download_single_image(remote_url: str) -> Optional[str]:
    """
    Download a single remote image into settings.DEMOPALS_ASSETS_DIR preserving its relative path structure.
    Returns the local web path (e.g., /assets/demopals/ops2meur/fra001-0.jpg).
    """
    if not remote_url or not remote_url.startswith("http"):
        return None

    try:
        parsed = urlparse(remote_url)
        path_parts = parsed.path.strip("/").split("/")
        if "demopals" in path_parts:
            idx = path_parts.index("demopals")
            rel_parts = path_parts[idx + 1:]
        else:
            rel_parts = path_parts[-2:] if len(path_parts) >= 2 else path_parts

        if not rel_parts:
            return None

        local_file_path = os.path.join(settings.DEMOPALS_ASSETS_DIR, *rel_parts)
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        if os.path.exists(local_file_path) and os.path.getsize(local_file_path) > 500:
            return f"/assets/demopals/{'/'.join(rel_parts)}"

        res = SESSION.get(remote_url, timeout=15)
        if res.status_code == 200 and len(res.content) > 500:
            with open(local_file_path, "wb") as f:
                f.write(res.content)
            return f"/assets/demopals/{'/'.join(rel_parts)}"
    except Exception as e:
        print(f"⚠️ Error downloading {remote_url}: {e}")
    return None


def probe_and_download_scans(base_section_url: str, img_key: str, max_scans: int = 6) -> List[Dict[str, str]]:
    """
    Probe candidate scan URLs for a given variant.
    Scans prioritized:
      - Scan 1 (-1.jpg): Slipcase / Cover Front
      - Scan 2 (-2.jpg): Disc Scan / Inlay
      - Scan 3 (-3.jpg): Slipcase / Cover Back
      - Scan 4 (-4.jpg): Inlay / Booklet Scan
      - Scan 0 (-0.jpg): Overview Thumbnail (Low-Res)
    """
    if not img_key:
        return []

    base_dir_url = base_section_url if base_section_url.endswith("/") else base_section_url.rsplit("/", 1)[0] + "/"

    scan_specs = [
        (1, "cover_front", "Slipcase / Cover Front"),
        (2, "disc_scan", "Disc Scan / Inlay"),
        (3, "cover_back", "Slipcase / Cover Back"),
        (4, "booklet_p1", "Inlay / Booklet Scan"),
        (5, "booklet_p2", "Alternate Scan #5"),
        (6, "booklet_p3", "Alternate Scan #6"),
        (0, "thumb_overview", "Overview Thumbnail (Low-Res)")
    ]

    scans = []
    for idx, scan_type, label in scan_specs:
        candidate_remote = urljoin(base_dir_url, f"{img_key}-{idx}.jpg")
        local_web_path = download_single_image(candidate_remote)
        if local_web_path:
            scans.append({
                "type": scan_type,
                "label": label,
                "remote_url": candidate_remote,
                "local_url": local_web_path
            })

    return scans


def download_demo_assets(demo: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Download all scans, variant covers, and flag icons for a demo disc."""
    section_url = demo.get("section_url", "")
    variants = demo.get("variants", [])
    best_primary_thumbnail = demo.get("primary_thumbnail")

    for v in variants:
        if v.get("flag_icon", "").startswith("http"):
            local_flag = download_single_image(v["flag_icon"])
            if local_flag:
                v["flag_icon"] = local_flag

        found_scans = probe_and_download_scans(section_url, v.get("img_key"))
        if found_scans:
            v["scans"] = found_scans
            front = next((s["local_url"] for s in found_scans if s["type"] == "cover_front"), None)
            if not best_primary_thumbnail or "-0.jpg" in best_primary_thumbnail or best_primary_thumbnail.startswith("http"):
                best_primary_thumbnail = front or found_scans[0]["local_url"]

    demo["variants"] = variants
    demo["primary_thumbnail"] = best_primary_thumbnail
    return demo


def download_all_demopals_assets(db_path: str = None, max_workers: int = 6, verbose: bool = True) -> Dict[str, Any]:
    """Batch download all demo disc artwork from Crimson Ceremony into local storage."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM demos")
    rows = cur.fetchall()
    conn.close()

    total_demos = len(rows)
    if verbose:
        print(f"\n========================================================")
        print(f"📦 Starting Offline Scans Download for {total_demos} Demos")
        print(f"========================================================\n")

    demos_data = []
    for r in rows:
        d = dict(r)
        d["variants"] = json.loads(d["variants_json"] or "[]")
        demos_data.append(d)

    processed = 0
    updated_demos = []

    def _worker(demo):
        return download_demo_assets(demo, verbose=False)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for updated_demo in executor.map(_worker, demos_data):
            processed += 1
            updated_demos.append(updated_demo)
            if verbose and processed % 25 == 0:
                print(f"[{processed}/{total_demos}] Downloaded assets for '{updated_demo['title']}'...")

    # Update database records
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    for d in updated_demos:
        cur.execute("""
        UPDATE demos 
        SET variants_json = ?, primary_thumbnail = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (json.dumps(d.get("variants", [])), d.get("primary_thumbnail"), d["id"]))

    conn.commit()
    conn.close()

    if verbose:
        print(f"\n✅ Finished downloading offline assets for {total_demos} demos!\n")

    return {
        "status": "completed",
        "total_processed": total_demos
    }
