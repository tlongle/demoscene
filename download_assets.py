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

import db

ASSETS_DIR = os.environ.get("ASSETS_DIR", "data/assets")
DEMOPALS_ASSETS_DIR = os.path.join(ASSETS_DIR, "demopals")
os.makedirs(DEMOPALS_ASSETS_DIR, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PlayStationDemoCollector/2.0"
})


def download_single_image(remote_url: str) -> Optional[str]:
    """
    Download a single remote image into DEMOPALS_ASSETS_DIR preserving its relative path structure.
    Returns the local web path (e.g., /assets/demopals/ops2meur/fra001-0.jpg).
    """
    if not remote_url or "noimg.jpg" in remote_url:
        return None

    try:
        parsed = urlparse(remote_url)
        # e.g. /demopals/ops2meur/fra001-0.jpg or /f-fra.jpg
        path_parts = parsed.path.lstrip("/").split("/")
        
        # Determine local subdirectory and filename
        if path_parts[0] == "demopals" and len(path_parts) > 1:
            rel_subpath = "/".join(path_parts[1:])  # ops2meur/fra001-0.jpg
        else:
            rel_subpath = "/".join(path_parts)      # f-fra.jpg

        local_file_path = os.path.join(DEMOPALS_ASSETS_DIR, rel_subpath)
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        if not os.path.exists(local_file_path) or os.path.getsize(local_file_path) == 0:
            res = SESSION.get(remote_url, timeout=12)
            if res.status_code == 200:
                with open(local_file_path, "wb") as f:
                    f.write(res.content)
            elif res.status_code == 404:
                return None
            else:
                return None

        # Return local web-accessible path
        return f"/assets/demopals/{rel_subpath}"
    except Exception as e:
        return None


def probe_and_download_scans(base_section_url: str, img_key: str, max_scans: int = 6) -> List[Dict[str, str]]:
    """
    Download and classify scans: High-res Cover Front (-1.jpg) and Disc Scan (-2.jpg) first,
    extras (-3.jpg+) next, and low-res thumbnail (-0.jpg) last.
    """
    if not img_key:
        return []

    folder_url = base_section_url.rsplit("/", 1)[0] + "/"
    scans = []

    # 1. High-Res Front Cover / Slipcase (-1.jpg)
    c1_remote = f"{folder_url}{img_key}-1.jpg"
    c1_local = download_single_image(c1_remote)
    if c1_local:
        scans.append({
            "type": "cover_front",
            "label": "Slipcase / Cover Front",
            "local_url": c1_local,
            "remote_url": c1_remote
        })

    # 2. High-Res Disc Scan / Inlay (-2.jpg)
    c2_remote = f"{folder_url}{img_key}-2.jpg"
    c2_local = download_single_image(c2_remote)
    if c2_local:
        scans.append({
            "type": "disc_scan",
            "label": "Disc Scan / Inlay",
            "local_url": c2_local,
            "remote_url": c2_remote
        })

    # 3. High-Res Cover Back / Slipcase Rear (-3.jpg+)
    labels = {
        3: "Slipcase / Cover Back",
        4: "Inlay / Booklet Scan",
        5: "Alternate Scan",
        6: "Alternate Scan"
    }
    for i in range(3, max_scans + 1):
        remote_url = f"{folder_url}{img_key}-{i}.jpg"
        local_path = download_single_image(remote_url)
        if local_path:
            scans.append({
                "type": "alternate_art",
                "label": labels.get(i, f"Alternate Scan #{i}"),
                "local_url": local_path,
                "remote_url": remote_url
            })
        else:
            if i > 3:
                break

    # 4. Low-res disc thumbnail (-0.jpg) at the end as an extra
    disc_remote = f"{folder_url}{img_key}-0.jpg"
    disc_local = download_single_image(disc_remote)
    if disc_local:
        scans.append({
            "type": "thumb_overview",
            "label": "Overview Thumbnail (Low-Res)",
            "local_url": disc_local,
            "remote_url": disc_remote
        })

    return scans


def download_all_demopals_assets(max_workers: int = 8, verbose: bool = True) -> Dict[str, Any]:
    """
    Download all disc images, country flags, and scans from the database into local storage.
    Updates SQLite with local asset paths.
    """
    start_time = time.time()
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, section_url, variants_json, primary_thumbnail FROM demos")
    demos = [dict(r) for r in cur.fetchall()]
    conn.close()

    if verbose:
        print(f"📥 Starting asset download for {len(demos)} demo discs (using {max_workers} threads)...")

    total_images_downloaded = 0

    def process_demo(demo):
        nonlocal total_images_downloaded
        demo_id = demo["id"]
        section_url = demo["section_url"]
        variants = json.loads(demo["variants_json"] or "[]")
        updated = False

        for v in variants:
            img_key = v.get("img_key")
            # 1. Download flag icon
            if v.get("flag_icon") and v["flag_icon"].startswith("http"):
                local_flag = download_single_image(v["flag_icon"])
                if local_flag:
                    v["local_flag_icon"] = local_flag
                    updated = True

            # 2. Download thumbnail
            if v.get("thumbnail") and v["thumbnail"].startswith("http"):
                local_thumb = download_single_image(v["thumbnail"])
                if local_thumb:
                    v["local_thumbnail"] = local_thumb
                    updated = True

            # 3. Probe and download high-res disc & slipcase scans
            if img_key:
                scans = probe_and_download_scans(section_url, img_key)
                if scans:
                    v["scans"] = scans
                    v["alternate_art"] = [s for s in scans if s["type"] != "disc_face"]
                    total_images_downloaded += len(scans)
                    updated = True

        if updated:
            # Determine local primary thumbnail
            local_primary = None
            for v in variants:
                if v.get("local_thumbnail"):
                    local_primary = v["local_thumbnail"]
                    break

            # Save back to database
            c = db.get_db_connection()
            cr = c.cursor()
            cr.execute("""
                UPDATE demos 
                SET variants_json = ?, primary_thumbnail = COALESCE(?, primary_thumbnail), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (json.dumps(variants), local_primary, demo_id))
            c.commit()
            c.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(process_demo, demos))

    elapsed = round(time.time() - start_time, 2)
    if verbose:
        print(f"✨ Downloaded and organized offline assets in {elapsed}s!")
        print(f"📁 Local assets directory: {DEMOPALS_ASSETS_DIR}")

    return {
        "success": True,
        "total_demos_processed": len(demos),
        "elapsed_seconds": elapsed,
        "assets_dir": DEMOPALS_ASSETS_DIR
    }


if __name__ == "__main__":
    download_all_demopals_assets(verbose=True)
