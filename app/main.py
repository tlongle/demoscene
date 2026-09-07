"""
FastAPI Server for PlayStation Demo & Promo Archive (PBPX).
Supports Docker containerization, Nginx reverse proxy, Cloudflare Tunnels, and local asset caching.
"""
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
import base64
import json
import secrets
import time

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Depends, Security, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from app.core.config import settings
import app.core.database as db
from app.core import auth
from app.services import scraper
from app.services import intel as game_intel
from app.services import downloader as download_assets
from app.services import boxart as boxart_service
from app.services import asset_pack
from app.services import redump as redump_service
from app.services import uploads as upload_service

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize directories and database on startup."""
    settings.ensure_dirs()
    db.init_db()

    # Pre-seed verified catalog on first run if database is fresh
    try:
        total_in_db = db.get_stats(user_id=None)["total_demos"]
        if total_in_db == 0:
            seed_path = db.get_catalog_seed_path()
            if seed_path and os.path.exists(seed_path):
                count = scraper.seed_database_from_file(seed_path)
                print(f"[PBPX] Auto-seeded {count} verified demo discs.")
    except Exception as e:
        print(f"[PBPX Warning] Catalog seeding check encountered: {e}")

    # In public web mode, ensure built-in artwork pack is pulled in background if missing
    if settings.is_public and asset_pack.count_local_assets() < 100:
        print("[PBPX Public Mode] Assets missing in storage; starting server-side background pull...")
        asset_pack.start_asset_pack_download()

    yield


app = FastAPI(
    title="PBPX",
    description="PlayStation Demo & Promo Archive - Track, preserve, and showcase PS1 & PS2 demo discs, scans, and box art",
    version="2.1.0",
    lifespan=lifespan
)

# Safe CORS policy
origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if not origins or "*" in origins:
    origins = ["*"]


async def verify_admin_key(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    user: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)
):
    """
    Verify administrator access via:
    1. Active user session (Cookie / Bearer / X-Session-Token) with is_admin=True
    2. Admin API key header (legacy / CLI / test fallback)
    3. Open local access if not public, no users created, and no ADMIN_API_KEY set
    """
    if user and user.get("is_admin"):
        return user

    configured_key = settings.ADMIN_API_KEY
    if configured_key:
        if api_key and secrets.compare_digest(api_key.strip(), configured_key):
            return {"id": 1, "username": "admin_key", "is_admin": True}
        raise HTTPException(
            status_code=401,
            detail="Administrator login required. Please log in as an administrator."
        )

    # If self-hosted and no users have been registered yet, allow setup/local access
    if not settings.is_public and auth.count_users() == 0:
        return {"id": 1, "username": "local_dev", "is_admin": True}

    raise HTTPException(
        status_code=401,
        detail="Administrator login required. Please log in as an administrator."
    )


async def get_collection_user(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    user: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)
) -> Dict[str, Any]:
    """
    Identify active user for personal collection mutations:
    1. Authenticated user session
    2. Admin API key header (legacy fallback -> maps to user 1)
    3. Open local development fallback (if selfhosted and 0 users)
    """
    if user:
        return user

    configured_key = settings.ADMIN_API_KEY
    if configured_key and api_key and secrets.compare_digest(api_key.strip(), configured_key):
        return {"id": 1, "username": "admin_key", "is_admin": True}

    if not settings.is_public and auth.count_users() == 0 and not configured_key:
        return {"id": 1, "username": "local_dev", "is_admin": True}

    raise HTTPException(
        status_code=401,
        detail="Please log in to manage your collection."
    )


def resolve_read_user_id(user: Optional[Dict[str, Any]]) -> Optional[int]:
    """Determine user_id for collection filtering in read endpoints."""
    if user:
        return user["id"]
    if not settings.is_public and auth.count_users() <= 1:
        return 1
    return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=30 * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.is_public
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    response.delete_cookie("demoscene_session")


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Lightweight in-memory rate limiting for auth endpoints (15 attempts / minute / IP)
_auth_rate_limits: dict[str, list[float]] = defaultdict(list)


def check_auth_rate_limit(request: Request, limit: int = 15, window_sec: int = 60) -> None:
    client_ip = request.client.host if request.client else "unknown"
    cf_ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    ip = cf_ip.split(",")[0].strip() if cf_ip else client_ip
    now = time.time()
    attempts = [t for t in _auth_rate_limits[ip] if now - t < window_sec]
    if len(attempts) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a minute before trying again.")
    attempts.append(now)
    _auth_rate_limits[ip] = attempts



class SettingsPayload(BaseModel):
    twitch_client_id: str
    twitch_client_secret: str


class CollectionUpdate(BaseModel):
    variant_id: str = "default"
    status: str = "owned"  # 'owned', 'wanted', 'unowned'
    condition: Optional[str] = "good"
    has_sleeve: Optional[int] = 1
    has_case: Optional[int] = 1
    is_working: Optional[int] = 1
    notes: Optional[str] = ""


class BulkCollectionUpdate(BaseModel):
    demo_ids: List[str]
    variant_id: str = "default"
    status: Optional[str] = None       # 'owned', 'wanted', 'unowned'
    condition: Optional[str] = None    # 'disc_only', 'mint', 'good', 'acceptable', 'poor'
    has_sleeve: Optional[int] = None   # 0 or 1
    has_case: Optional[int] = None     # 0 or 1
    is_working: Optional[int] = None   # 0 or 1
    notes: Optional[str] = None


class ImportPayload(BaseModel):
    version: int = 1
    collection: List[Dict[str, Any]]


class LoginPayload(BaseModel):
    username: str
    password: str


class SetupPayload(BaseModel):
    username: str
    password: str


class RegisterPayload(BaseModel):
    username: str
    password: str


class PrivacyPayload(BaseModel):
    is_private: bool


class ManualDemoPayload(BaseModel):
    title: str
    console: str = "PS2"
    section_name: Optional[str] = "Community Demos"
    sced_codes: Optional[List[str]] = []
    country: Optional[str] = "Europe"
    categories: Optional[Dict[str, List[str]]] = {}
    notes: Optional[str] = ""
    primary_thumbnail: Optional[str] = ""


class UpdateDemoPayload(BaseModel):
    title: Optional[str] = None
    console: Optional[str] = None
    section_name: Optional[str] = None
    sced_codes: Optional[List[str]] = None
    categories: Optional[Dict[str, List[str]]] = None
    notes: Optional[str] = None
    primary_thumbnail: Optional[str] = None


class RedumpImportPayload(BaseModel):
    redump_id: int
    custom_title: Optional[str] = None
    playable_games: Optional[List[str]] = None
    notes: Optional[str] = None


class ScanUploadPayload(BaseModel):
    image_base64: str
    filename: Optional[str] = "scan.jpg"
    scan_type: str = "cover_front"
    variant_idx: int = 0


@app.get("/api/auth/me")
async def get_current_user_profile(user: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)):
    """Return active user profile, instance mode, and setup status."""
    user_count = auth.count_users()
    return {
        "authenticated": user is not None,
        "user": user,
        "setup_needed": (not settings.is_public and user_count == 0),
        "mode": settings.MODE,
        "is_public": settings.is_public,
        "registration_allowed": settings.is_public or settings.ALLOW_REGISTRATION or (user_count == 0)
    }


@app.post("/api/auth/setup")
async def setup_admin_account(payload: SetupPayload, response: Response):
    """Initial setup wizard for Master Admin username & password."""
    if auth.count_users() > 0:
        raise HTTPException(status_code=400, detail="Setup already completed. Please log in.")
    try:
        user = auth.create_user(payload.username, payload.password, is_admin=True)
        token = auth.create_session(user["id"])
        set_session_cookie(response, token)
        return {"success": True, "token": token, "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/register")
async def register_account(request: Request, payload: RegisterPayload, response: Response):
    """Register a new collector account."""
    check_auth_rate_limit(request)
    user_count = auth.count_users()
    if not settings.is_public and user_count > 0 and not settings.ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=403,
            detail="Public registration is disabled on this self-hosted instance."
        )

    # First user is admin; subsequent users are standard collectors
    is_admin = (user_count == 0)
    try:
        user = auth.create_user(payload.username, payload.password, is_admin=is_admin)
        token = auth.create_session(user["id"])
        set_session_cookie(response, token)
        return {"success": True, "token": token, "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
async def login_account(request: Request, payload: LoginPayload, response: Response):
    """Authenticate username and password, returning session token and cookie."""
    check_auth_rate_limit(request)
    user = auth.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = auth.create_session(user["id"])
    set_session_cookie(response, token)
    return {"success": True, "token": token, "user": user}


@app.post("/api/auth/logout")
async def logout_account(
    request: Request,
    response: Response,
    user: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)
):
    """Invalidate active session and clear cookie."""
    token = auth.extract_session_token(request)
    if token:
        auth.destroy_session(token)
    clear_session_cookie(response)
    return {"success": True}


@app.post("/api/auth/privacy")
def update_privacy(payload: PrivacyPayload, user: Dict[str, Any] = Depends(auth.get_current_user)):
    """Update privacy preference for user collection profile."""
    db.update_user_privacy(user["id"], payload.is_private)
    return {"success": True, "is_private": payload.is_private}


@app.get("/api/users/{username}/collection")
def get_user_public_collection(
    username: str,
    viewer: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)
):
    """Public collector showcase profile."""
    target_user = db.get_user_by_username(username)
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Collector '{username}' not found.")

    is_owner = viewer and (viewer["id"] == target_user["id"])
    is_admin_viewer = viewer and viewer.get("is_admin")
    if target_user.get("is_private") and not (is_owner or is_admin_viewer):
        return {
            "username": target_user["username"],
            "is_private": True,
            "message": "This collector has set their collection to private."
        }

    stats = db.get_stats(user_id=target_user["id"])
    owned_demos = db.search_demos(collection_status="owned", user_id=target_user["id"], limit=300)
    return {
        "username": target_user["username"],
        "is_private": False,
        "stats": stats,
        "total_owned": owned_demos["total"],
        "discs": owned_demos["results"]
    }


@app.get("/api/settings")
def get_settings():
    """Get current configuration status for IGDB API."""
    return boxart_service.get_igdb_status()


@app.post("/api/settings", dependencies=[Depends(verify_admin_key)])
def update_settings(payload: SettingsPayload):
    """Test and update IGDB API credentials, writing to .env."""
    if settings.is_public:
        raise HTTPException(
            status_code=403,
            detail="Twitch credentials cannot be modified via UI in public web mode."
        )
    res = boxart_service.save_igdb_credentials(
        payload.twitch_client_id,
        payload.twitch_client_secret
    )
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to verify credentials"))
    return res


# Mount local assets for disc photos, slipcase scans, and box art
app.mount("/assets", StaticFiles(directory=settings.ASSETS_DIR), name="assets")


@app.get("/api/demos")
def get_demos(
    q: str = Query("", description="Search term across title, SCED, game names"),
    console: str = Query("ALL", description="Console filter: ALL, PS1, PS2"),
    section: str = Query("ALL", description="Section name filter"),
    country: str = Query("ALL", description="Country/region filter"),
    status: str = Query("ALL", description="Collection status: ALL, owned, wanted, unowned"),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)
):
    """Search and filter demo discs with pagination."""
    user_id = resolve_read_user_id(user)
    return db.search_demos(
        query=q,
        console=console,
        section_name=section,
        country=country,
        collection_status=status,
        limit=limit,
        offset=offset,
        user_id=user_id
    )


@app.get("/api/demos/{demo_id}")
def get_demo_detail(
    demo_id: str,
    user: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)
):
    """Retrieve full details of a specific demo disc, including games, scans, and intel."""
    user_id = resolve_read_user_id(user)
    demo = db.get_demo(demo_id, user_id=user_id)
    if not demo:
        raise HTTPException(status_code=404, detail="Demo disc not found")
    
    # Enrich game categories from cache (instant, non-blocking)
    demo["enriched_categories"] = game_intel.enrich_demo_contents(
        demo.get("categories", {}),
        console=demo.get("console", "PS2"),
        auto_fetch=False
    )
    return demo


@app.post("/api/collection/bulk")
def bulk_update_collection_status(
    payload: BulkCollectionUpdate,
    user: Dict[str, Any] = Depends(get_collection_user)
):
    """Bulk update collection status, condition, and checklist attributes for multiple demos."""
    if not payload.demo_ids:
        raise HTTPException(status_code=400, detail="demo_ids list cannot be empty")

    updates = {}
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.condition is not None:
        updates["condition"] = payload.condition
    if payload.has_sleeve is not None:
        updates["has_sleeve"] = payload.has_sleeve
    if payload.has_case is not None:
        updates["has_case"] = payload.has_case
    if payload.is_working is not None:
        updates["is_working"] = payload.is_working
    if payload.notes is not None:
        updates["notes"] = payload.notes

    updated_count = db.bulk_update_collection(
        demo_ids=payload.demo_ids,
        updates=updates,
        variant_id=payload.variant_id,
        user_id=user["id"]
    )
    return {"success": True, "updated_count": updated_count}


@app.post("/api/collection/{demo_id}")
def update_collection_status(
    demo_id: str,
    payload: CollectionUpdate,
    user: Dict[str, Any] = Depends(get_collection_user)
):
    """Update collection tracking state for a demo disc/variant."""
    demo = db.get_demo(demo_id, user_id=user["id"])
    if not demo:
        raise HTTPException(status_code=404, detail="Demo disc not found")

    result = db.update_collection(
        demo_id=demo_id,
        variant_id=payload.variant_id,
        status=payload.status,
        condition=payload.condition or "good",
        has_sleeve=payload.has_sleeve if payload.has_sleeve is not None else 1,
        has_case=payload.has_case if payload.has_case is not None else 1,
        is_working=payload.is_working if payload.is_working is not None else 1,
        notes=payload.notes or "",
        user_id=user["id"]
    )
    return {"success": True, "record": result}


@app.get("/api/stats")
def get_collection_stats(user: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)):
    """Retrieve collection statistics, counts, and completion rate."""
    user_id = resolve_read_user_id(user)
    return db.get_stats(user_id=user_id)


@app.get("/api/collection/games")
def get_collection_games(user: Optional[Dict[str, Any]] = Depends(auth.get_current_user_optional)):
    """Retrieve all unique games contained within owned demo discs."""
    user_id = resolve_read_user_id(user)
    return db.get_collection_games(user_id=user_id)


@app.get("/api/filters")
def get_filter_options():
    """Retrieve unique filter options (consoles, sections, countries)."""
    conn = db.get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT console, section_name FROM demos ORDER BY console, section_name")
    sections = [{"console": r["console"], "name": r["section_name"]} for r in cur.fetchall()]

    cur.execute("SELECT DISTINCT variants_json FROM demos")
    all_variants_raw = cur.fetchall()
    countries = set()
    for row in all_variants_raw:
        if row[0]:
            try:
                v_list = json.loads(row[0])
                for v in v_list:
                    if v.get("country"):
                        countries.add(v["country"])
            except Exception:
                pass

    conn.close()
    return {
        "consoles": ["PS1", "PS2"],
        "sections": sections,
        "countries": sorted(list(countries))
    }


@app.get("/api/export")
def export_backup(user: Dict[str, Any] = Depends(get_collection_user)):
    """Export complete collection data for JSON backup."""
    return db.export_collection_data(user_id=user["id"])


@app.post("/api/import")
def import_backup(payload: ImportPayload, user: Dict[str, Any] = Depends(get_collection_user)):
    """Import and merge JSON backup collection records."""
    count = db.import_collection_data(payload.dict(), user_id=user["id"])
    return {"success": True, "imported_count": count}


@app.post("/api/scrape", dependencies=[Depends(verify_admin_key)])
def trigger_scrape():
    """Check Crimson Ceremony for new releases and perform targeted incremental sync."""
    result = scraper.peek_and_sync_updates(verbose=True)
    return {
        "success": result.get("status") != "error",
        "status": result.get("status"),
        "message": result.get("message") or result.get("error", "Update check complete."),
        "new_discs_added": result.get("new_discs_added", 0),
        "last_synced_date": result.get("last_synced_date", "")
    }




@app.post("/api/boxart/fetch-all", dependencies=[Depends(verify_admin_key)])
def trigger_boxart_fetch(background_tasks: BackgroundTasks, limit: int = 150):
    """Trigger batch resolution and download of game box art."""
    if settings.is_public:
        raise HTTPException(
            status_code=403,
            detail="Box art batch fetch is server-managed and unavailable in public web mode."
        )
    background_tasks.add_task(boxart_service.batch_fetch_boxart, limit=limit)
    return {"success": True, "message": f"Box art download queued for up to {limit} games."}


@app.get("/api/assets/pack/status")
def get_pack_status():
    """Check status of local assets and any active pack download task."""
    status = asset_pack.get_asset_pack_status()
    if settings.is_public:
        status["assets_ready"] = True
    return status


class AssetPackDownloadPayload(BaseModel):
    url: Optional[str] = None


@app.post("/api/assets/pack/download", dependencies=[Depends(verify_admin_key)])
def download_asset_pack(payload: Optional[AssetPackDownloadPayload] = None):
    """Trigger 1-click download & extraction of complete pre-packaged artwork bundle."""
    if settings.is_public:
        raise HTTPException(
            status_code=403,
            detail="Artwork bundle download via UI is disabled in public web mode. Media assets are pre-installed on the server."
        )
    custom_url = payload.url if payload else None
    res = asset_pack.start_asset_pack_download(custom_url)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res["message"])
    return res


# ==========================================================================
# Master Database Admin & Redump Endpoints
# ==========================================================================
@app.get("/api/admin/redump/search", dependencies=[Depends(verify_admin_key)])
def search_redump_discs(q: str = Query(..., min_length=1), console: Optional[str] = None):
    """Search Redump.org discs for PS1 and PS2."""
    results = redump_service.search_redump(q, system_filter=console)
    return {"query": q, "results": results}


@app.post("/api/admin/redump/import", dependencies=[Depends(verify_admin_key)])
def import_redump_disc(payload: RedumpImportPayload):
    """1-Click import disc from Redump.org into master database."""
    try:
        demo = redump_service.import_redump_disc(
            payload.redump_id,
            custom_title=payload.custom_title,
            playable_games=payload.playable_games,
            notes=payload.notes
        )
        return {"success": True, "demo": demo}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/admin/demos", dependencies=[Depends(verify_admin_key)])
def create_demo_entry(payload: ManualDemoPayload):
    """Create a new manual demo disc entry."""
    demo = db.create_manual_demo(payload.model_dump())
    return {"success": True, "demo": demo}


@app.put("/api/admin/demos/{demo_id}", dependencies=[Depends(verify_admin_key)])
def update_demo_entry(demo_id: str, payload: UpdateDemoPayload):
    """Update metadata for an existing disc."""
    demo = db.update_demo(demo_id, payload.model_dump(exclude_unset=True))
    if not demo:
        raise HTTPException(status_code=404, detail="Demo disc not found")
    return {"success": True, "demo": demo}


@app.delete("/api/admin/demos/{demo_id}", dependencies=[Depends(verify_admin_key)])
def delete_demo_entry(demo_id: str):
    """Delete a demo disc from master database."""
    success = db.delete_demo(demo_id)
    if not success:
        raise HTTPException(status_code=404, detail="Demo disc not found")
    return {"success": True}


@app.post("/api/admin/demos/{demo_id}/scans", dependencies=[Depends(verify_admin_key)])
def upload_demo_scan(demo_id: str, payload: ScanUploadPayload):
    """Upload a physical photo, scan, or slipcase image (Base64 data URL or raw Base64)."""
    raw_b64 = payload.image_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    try:
        content = base64.b64decode(raw_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    return upload_service.save_demo_scan_bytes(
        demo_id=demo_id,
        content=content,
        filename=payload.filename or "scan.jpg",
        scan_type=payload.scan_type,
        variant_idx=payload.variant_idx
    )


# Mount static files directory
app.mount("/", StaticFiles(directory=settings.STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)

