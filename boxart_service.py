"""
PlayStation Box Art & Media Art Service.
Uses official IGDB (Twitch API) exclusively for game cover art resolution,
with local persistent disk caching in data/assets/boxart/.
"""
import os
import re
import json
import time
import requests
from typing import Optional, Dict, Any, List

import db

ASSETS_DIR = os.environ.get("ASSETS_DIR", "data/assets")
BOXART_DIR = os.path.join(ASSETS_DIR, "boxart")
os.makedirs(BOXART_DIR, exist_ok=True)

# Twitch / IGDB Credentials
IGDB_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "")
IGDB_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")
_igdb_token: Optional[str] = None
_token_expiry: float = 0

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "PlayStationDemoSceneCollector/2.0"
})

NON_GAME_PATTERNS = [
    r"voyage of emotion", r"interview", r"making of", r"behind the scenes",
    r"trailer", r"teaser", r"commercial", r"showreel", r"gt3 fest", r"aibo",
    r"retrospective", r"ps2 video", r"production interview", r"e3 video",
    r"manga video", r"dinner at chez claude", r"project y", r"uk\.playstation\.com",
    r"www\.playstation\.com", r"sony cm", r"scee cm"
]


def is_non_game_media(item_name: str) -> bool:
    """Check if item is a video, making-of, interview, or non-game extra."""
    name_lower = item_name.lower()
    return any(re.search(pat, name_lower) for pat in NON_GAME_PATTERNS)


def sanitize_filename(name: str) -> str:
    """Sanitize game name for local file storage."""
    clean = re.sub(r"[^\w\-_.]", "_", name.strip().lower())
    return clean[:70]


def get_igdb_status() -> Dict[str, Any]:
    """Check current IGDB configuration status."""
    client_id = os.environ.get("TWITCH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
    is_configured = bool(client_id and client_secret)
    masked_id = f"{client_id[:4]}...{client_id[-4:]}" if len(client_id) > 8 else ("Set" if client_id else "")
    
    return {
        "configured": is_configured,
        "client_id_masked": masked_id,
        "has_secret": bool(client_secret)
    }


def save_igdb_credentials(client_id: str, client_secret: str, env_file_path: str = ".env") -> Dict[str, Any]:
    """Test and save Twitch / IGDB credentials to environment and .env file."""
    client_id = client_id.strip()
    client_secret = client_secret.strip()

    # 1. Test credentials against Twitch token endpoint
    test_result = test_twitch_credentials(client_id, client_secret)
    if not test_result["success"]:
        return test_result

    # 2. Update runtime environment
    global IGDB_CLIENT_ID, IGDB_CLIENT_SECRET, _igdb_token, _token_expiry
    os.environ["TWITCH_CLIENT_ID"] = client_id
    os.environ["TWITCH_CLIENT_SECRET"] = client_secret
    IGDB_CLIENT_ID = client_id
    IGDB_CLIENT_SECRET = client_secret
    _igdb_token = test_result["token"]
    _token_expiry = time.time() + test_result.get("expires_in", 3600) - 300

    # 3. Write or update .env file
    try:
        env_lines = []
        if os.path.exists(env_file_path):
            with open(env_file_path, "r") as f:
                for line in f:
                    if line.startswith("TWITCH_CLIENT_ID=") or line.startswith("TWITCH_CLIENT_SECRET="):
                        continue
                    env_lines.append(line)

        env_lines.append(f"TWITCH_CLIENT_ID={client_id}\n")
        env_lines.append(f"TWITCH_CLIENT_SECRET={client_secret}\n")

        with open(env_file_path, "w") as f:
            f.writelines(env_lines)
    except Exception as e:
        print(f"⚠️ Warning: Could not write to .env file: {e}")

    return {
        "success": True,
        "message": "Twitch / IGDB credentials verified and saved successfully!"
    }


def test_twitch_credentials(client_id: str, client_secret: str) -> Dict[str, Any]:
    """Test Twitch OAuth client_credentials grant."""
    if not client_id or not client_secret:
        return {"success": False, "error": "Client ID and Client Secret are required."}

    try:
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials"
        }
        res = requests.post(url, params=params, timeout=8)
        if res.status_code == 200:
            data = res.json()
            return {
                "success": True,
                "token": data.get("access_token"),
                "expires_in": data.get("expires_in", 3600)
            }
        else:
            err_msg = res.json().get("message", "Invalid Twitch credentials")
            return {"success": False, "error": f"Twitch Error ({res.status_code}): {err_msg}"}
    except Exception as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}


def get_igdb_access_token() -> Optional[str]:
    """Obtain or refresh Twitch OAuth token for IGDB."""
    global _igdb_token, _token_expiry
    client_id = os.environ.get("TWITCH_CLIENT_ID", "").strip()
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        return None

    if _igdb_token and time.time() < _token_expiry:
        return _igdb_token

    test = test_twitch_credentials(client_id, client_secret)
    if test["success"]:
        _igdb_token = test["token"]
        _token_expiry = time.time() + test.get("expires_in", 3600) - 300
        return _igdb_token

    return None


def get_cached_boxart_path(game_name: str, console: str = "PS2") -> Optional[str]:
    """Check if box art exists in SQLite or locally on disk."""
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT cover_url FROM game_covers WHERE game_name = ?", (game_name,))
    row = cur.fetchone()
    conn.close()

    if row and row[0]:
        local_path = row[0]
        if os.path.exists(local_path.lstrip("/")):
            return local_path

    slug = sanitize_filename(f"{console}_{game_name}")
    for ext in [".jpg", ".png", ".webp"]:
        candidate = os.path.join(BOXART_DIR, f"{slug}{ext}")
        if os.path.exists(candidate):
            url_path = f"/assets/boxart/{slug}{ext}"
            record_boxart(game_name, url_path, "disk")
            return url_path

    return None


def record_boxart(game_name: str, cover_url: str, source: str = "igdb") -> None:
    """Record box art URL into SQLite."""
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO game_covers (game_name, cover_url, source, updated_at)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(game_name) DO UPDATE SET
        cover_url=excluded.cover_url,
        source=excluded.source,
        updated_at=CURRENT_TIMESTAMP
    """, (game_name, cover_url, source))
    conn.commit()
    conn.close()


def download_and_save_boxart(image_url: str, game_name: str, console: str = "PS2") -> Optional[str]:
    """Download image URL and save to local boxart directory."""
    if not image_url:
        return None
    try:
        clean_url = image_url.split("?")[0]
        if clean_url.startswith("//"):
            clean_url = f"https:{clean_url}"

        res = SESSION.get(clean_url, timeout=12)
        if res.status_code != 200 or len(res.content) < 1500:
            return None

        ext = ".jpg"
        if clean_url.lower().endswith(".png"):
            ext = ".png"
        elif clean_url.lower().endswith(".webp"):
            ext = ".webp"

        slug = sanitize_filename(f"{console}_{game_name}")
        file_name = f"{slug}{ext}"
        file_path = os.path.join(BOXART_DIR, file_name)

        with open(file_path, "wb") as f:
            f.write(res.content)

        web_path = f"/assets/boxart/{file_name}"
        record_boxart(game_name, web_path, "igdb")
        return web_path
    except Exception:
        return None


def fetch_igdb_boxart(game_name: str, console: str = "PS2") -> Optional[str]:
    """Fetch official high-res box art from IGDB."""
    token = get_igdb_access_token()
    client_id = os.environ.get("TWITCH_CLIENT_ID", "").strip()
    if not token or not client_id:
        return None

    clean_name = game_name.replace('"', '\\"').strip()
    platform_id = 7 if console == "PS1" else 8  # IGDB platform IDs: 7 = PS1, 8 = PS2

    # Query 1: Platform targeted
    query_targeted = f"""
    fields name, cover.image_id, cover.url;
    search "{clean_name}";
    where platforms = ({platform_id});
    limit 1;
    """

    try:
        url = "https://api.igdb.com/v4/games"
        headers = {
            "Client-ID": client_id,
            "Authorization": f"Bearer {token}"
        }
        res = requests.post(url, headers=headers, data=query_targeted, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if data and len(data) > 0 and data[0].get("cover"):
                img_id = data[0]["cover"].get("image_id")
                if img_id:
                    igdb_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{img_id}.jpg"
                    return download_and_save_boxart(igdb_url, game_name, console)

        # Query 2: General search fallback if platform targeted yielded nothing
        query_general = f"""
        fields name, cover.image_id, cover.url;
        search "{clean_name}";
        limit 1;
        """
        res2 = requests.post(url, headers=headers, data=query_general, timeout=8)
        if res2.status_code == 200:
            data2 = res2.json()
            if data2 and len(data2) > 0 and data2[0].get("cover"):
                img_id = data2[0]["cover"].get("image_id")
                if img_id:
                    igdb_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{img_id}.jpg"
                    return download_and_save_boxart(igdb_url, game_name, console)
    except Exception:
        pass

    return None


def resolve_game_boxart(game_name: str, console: str = "PS2", auto_fetch: bool = True) -> Dict[str, Any]:
    """
    Resolve box art for a game title.
    Checks local cache first. If not cached, queries IGDB (if configured).
    If no IGDB credentials exist or game not found, returns retro badge placeholder.
    """
    if is_non_game_media(game_name):
        return {
            "type": "media_extra",
            "is_game": False,
            "cover_url": None,
            "label": "PlayStation Media"
        }

    # 1. Check local cache
    cached = get_cached_boxart_path(game_name, console)
    if cached:
        return {
            "type": "boxart",
            "is_game": True,
            "cover_url": cached,
            "source": "cache"
        }

    # 2. Query IGDB (Twitch API)
    if auto_fetch:
        igdb_path = fetch_igdb_boxart(game_name, console)
        if igdb_path:
            return {
                "type": "boxart",
                "is_game": True,
                "cover_url": igdb_path,
                "source": "igdb"
            }

    # 3. Clean fallback placeholder until IGDB is configured
    return {
        "type": "retro_badge",
        "is_game": True,
        "cover_url": None,
        "source": "generated"
    }


def batch_fetch_boxart(limit: int = 150, console: Optional[str] = None) -> Dict[str, int]:
    """Pre-fetch and download box art for games via IGDB."""
    conn = db.get_db_connection()
    cur = conn.cursor()
    where = f"WHERE console = '{console}'" if console else ""
    cur.execute(f"SELECT contents_json, console FROM demos {where}")
    rows = cur.fetchall()
    conn.close()

    unique_games = []
    seen = set()
    for row in rows:
        contents = json.loads(row[0] or "{}")
        cons = row[1]
        for cat, games in contents.items():
            for g in games:
                if not is_non_game_media(g) and g not in seen:
                    seen.add(g)
                    unique_games.append((g, cons))

    fetched = 0
    cached = 0
    for game_name, cons in unique_games[:limit]:
        if get_cached_boxart_path(game_name, cons):
            cached += 1
            continue

        res = resolve_game_boxart(game_name, cons, auto_fetch=True)
        if res.get("cover_url"):
            fetched += 1
        time.sleep(0.2)

    return {"total": len(unique_games), "newly_fetched": fetched, "already_cached": cached}
