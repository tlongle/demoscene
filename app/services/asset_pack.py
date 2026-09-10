"""
Asset Pack Download & Extraction Pipeline.
Handles 1-click downloading and extraction of pre-packaged high-res artwork scans (demoscene_assets.tar.gz)
from GitHub Releases CDN.
"""
import os
import tarfile
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional
import requests

from app.core.config import settings

# Thread-safe global state for asset pack operations
_LOCK = threading.Lock()
_STATUS = {
    "is_downloading": False,
    "percent": 0,
    "downloaded_mb": 0.0,
    "total_mb": 0.0,
    "stage": "idle",  # "idle", "downloading", "extracting", "completed", "error"
    "message": "",
    "error": None
}


def count_local_assets() -> int:
    """Count local artwork images in settings.DEMOPALS_ASSETS_DIR."""
    p = Path(settings.DEMOPALS_ASSETS_DIR)
    return sum(1 for _ in p.rglob("*.*")) if p.exists() else 0


def get_asset_pack_status() -> Dict[str, Any]:
    """Return status of local artwork and any active download/extraction task."""
    with _LOCK:
        status_copy = dict(_STATUS)

    local_count = count_local_assets()
    return {
        "assets_ready": local_count >= 100,
        "local_asset_count": local_count,
        "is_downloading": status_copy["is_downloading"],
        "percent": status_copy["percent"],
        "downloaded_mb": round(status_copy["downloaded_mb"], 1),
        "total_mb": round(status_copy["total_mb"], 1),
        "stage": status_copy["stage"],
        "message": status_copy["message"],
        "error": status_copy["error"],
        "default_url": settings.ASSET_PACK_URL
    }


def _run_download_and_extract(url: str) -> None:
    """Worker thread for downloading and extracting demoscene_assets.tar.gz."""
    global _STATUS
    download_target = Path(settings.DATA_DIR) / "demoscene_assets_download.tar.gz"

    try:
        with _LOCK:
            _STATUS["is_downloading"] = True
            _STATUS["stage"] = "downloading"
            _STATUS["percent"] = 0
            _STATUS["message"] = "Connecting to CDN..."
            _STATUS["error"] = None

        headers = {
            "User-Agent": "DEMOSCENE/2.0 (PlayStation Demo Collector)"
        }
        res = requests.get(url, headers=headers, stream=True, timeout=30)
        res.raise_for_status()

        total_size = int(res.headers.get("content-length", 0))
        total_mb = total_size / (1024 * 1024) if total_size else 0.0

        with _LOCK:
            _STATUS["total_mb"] = total_mb
            _STATUS["message"] = "Downloading artwork archive..."

        downloaded = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        with open(download_target, "wb") as f:
            for chunk in res.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                dl_mb = downloaded / (1024 * 1024)
                pct = int((downloaded / total_size) * 100) if total_size else 0

                with _LOCK:
                    _STATUS["downloaded_mb"] = dl_mb
                    _STATUS["percent"] = min(pct, 99)
                    _STATUS["message"] = f"Downloaded {dl_mb:.1f} MB of {total_mb:.1f} MB ({pct}%)"

        # Extraction stage
        with _LOCK:
            _STATUS["stage"] = "extracting"
            _STATUS["percent"] = 99
            _STATUS["message"] = "Extracting artwork files into data/assets/..."

        with tarfile.open(download_target, "r:gz") as tar:
            # Python 3.12+ safe extraction filter prevents path traversal and dangerous file types
            tar.extractall(path=str(settings.BASE_DIR), filter="data")

        # Cleanup archive
        if download_target.exists():
            download_target.unlink()

        final_count = count_local_assets()
        with _LOCK:
            _STATUS["is_downloading"] = False
            _STATUS["stage"] = "completed"
            _STATUS["percent"] = 100
            _STATUS["message"] = f"✓ Successfully installed {final_count} artwork covers and scans!"

    except Exception as e:
        if download_target.exists():
            try:
                download_target.unlink()
            except Exception:
                pass

        with _LOCK:
            _STATUS["is_downloading"] = False
            _STATUS["stage"] = "error"
            _STATUS["error"] = str(e)
            _STATUS["message"] = f"Failed to download asset pack: {e}"


def start_asset_pack_download(url: Optional[str] = None) -> Dict[str, Any]:
    """Trigger background download and extraction of artwork bundle."""
    with _LOCK:
        if _STATUS["is_downloading"]:
            return {
                "success": False,
                "message": "Download is already in progress.",
                "status": dict(_STATUS)
            }

    download_url = url or settings.ASSET_PACK_URL
    if not download_url:
        return {
            "success": False,
            "message": "No asset pack URL configured."
        }

    # Restrict custom URLs to HTTPS schemes and valid tar.gz formats
    from urllib.parse import urlparse
    parsed = urlparse(download_url)
    if parsed.scheme != "https" or not (download_url.endswith(".tar.gz") or download_url.endswith(".tgz")):
        return {
            "success": False,
            "message": "Invalid download URL. Must be an HTTPS link to a .tar.gz archive."
        }

    thread = threading.Thread(target=_run_download_and_extract, args=(download_url,), daemon=True)
    thread.start()

    return {
        "success": True,
        "message": "Artwork download started in background.",
        "url": download_url
    }
