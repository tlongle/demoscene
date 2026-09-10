"""
Scan & Image Upload Service for PBPX.
Handles saving user-uploaded disc photos, front covers, and inlay scans.
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import HTTPException

from app.core.config import settings
from app.core.database import get_db_connection, get_demo


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SCAN_LABELS = {
    "cover_front": ("Slipcase / Cover Front", "-1.jpg"),
    "disc_scan": ("High-Quality CD/DVD Scan", "-2.jpg"),
    "cover_back": ("Slipcase / Cover Back", "-3.jpg"),
    "inlay": ("Inlay / Booklet Scan", "-4.jpg")
}


def save_demo_scan_bytes(
    demo_id: str,
    content: bytes,
    filename: str = "scan.jpg",
    scan_type: str = "cover_front",
    variant_idx: int = 0,
    db_path: str = None
) -> Dict[str, Any]:
    """Save raw image bytes and attach to demo record."""
    demo = get_demo(demo_id, db_path=db_path)
    if not demo:
        raise HTTPException(status_code=404, detail="Demo disc not found")

    ext = Path(filename).suffix.lower()
    if not ext or ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    custom_dir = Path(settings.DEMOPALS_ASSETS_DIR) / "custom"
    custom_dir.mkdir(parents=True, exist_ok=True)

    safe_demo_id = re.sub(r"[^\w\-]", "_", demo_id.lower())
    label, suffix = SCAN_LABELS.get(scan_type, ("Uploaded Scan", f"_{scan_type}{ext}"))
    out_name = f"{safe_demo_id}{suffix}"
    dest_path = custom_dir / out_name

    if len(content) < 50:
        raise HTTPException(status_code=400, detail="Uploaded file is empty or corrupt")

    dest_path.write_bytes(content)
    web_url = f"/assets/demopals/custom/{out_name}"

    # Update demo variants and scans
    variants = demo.get("variants", [])
    if not variants:
        variants = [{
            "country": "Europe",
            "sced": demo.get("catalog_line", ""),
            "img_key": safe_demo_id,
            "thumb_img": web_url,
            "flag_icon": "/assets/demopals/f-eur.jpg",
            "scans": []
        }]

    if variant_idx >= len(variants):
        variant_idx = 0

    v = variants[variant_idx]
    scans = v.get("scans", [])

    # Replace existing scan of same type or append
    new_scan = {
        "type": scan_type,
        "label": label,
        "local_url": web_url,
        "remote_url": web_url
    }
    scans = [s for s in scans if s.get("type") != scan_type]
    scans.insert(0 if scan_type == "cover_front" else len(scans), new_scan)
    v["scans"] = scans
    v["thumb_img"] = web_url

    # Set as primary thumbnail if front cover or no primary thumb
    primary_thumb = demo.get("primary_thumbnail")
    if scan_type == "cover_front" or not primary_thumb or "placeholder" in primary_thumb:
        primary_thumb = web_url

    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    UPDATE demos SET
        variants_json = ?,
        primary_thumbnail = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (json.dumps(variants), primary_thumb, demo_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "url": web_url,
        "scan_type": scan_type,
        "label": label,
        "demo": get_demo(demo_id, db_path=db_path)
    }
