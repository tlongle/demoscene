"""
FastAPI Server for PlayStation Demo Collector (DEMOSCENE).
Supports Docker containerization, Nginx reverse proxy, Cloudflare Tunnels, and local asset caching.
"""
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
import base64
import json
import secrets

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
    yield


app = FastAPI(
    title="DEMOSCENE",
    description="Track and archive PS1 & PS2 demo discs, disc scans, slipcases, and box art",
    version="2.0.0",
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
    1. Active user session (Cookie / Bearer / X-Session-Token)
    2. Admin API key header (legacy / CLI / test fallback)
    3. Open local access if no users created and no ADMIN_API_KEY set
    """
    if user and user.get("is_admin"):
        return user

    configured_key = settings.ADMIN_API_KEY
    if configured_key:
        if api_key and secrets.compare_digest(api_key.strip(), configured_key):
            return {"id": 0, "username": "admin_key", "is_admin": True}
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required. Please log in."
        )

    # If no users have been registered yet, allow setup/local access
    if auth.count_users() == 0:
        return {"id": 0, "username": "local_dev", "is_admin": True}

    raise HTTPException(
        status_code=401,
        detail="Admin authentication required. Please log in."
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    """Return active user profile and whether first-time setup is needed."""
    user_count = auth.count_users()
    return {
        "authenticated": user is not None,
        "user": user,
        "setup_needed": user_count == 0
    }


@app.post("/api/auth/setup")
async def setup_admin_account(payload: SetupPayload, response: Response):
    """Initial setup wizard for Master Admin username & password."""
    if auth.count_users() > 0:
        raise HTTPException(status_code=400, detail="Setup already completed. Please log in.")
    try:
        user = auth.create_user(payload.username, payload.password, is_admin=True)
        token = auth.create_session(user["id"])
        response.set_cookie(
            key="demoscene_session",
            value=token,
            max_age=30 * 86400,
            httponly=True,
            samesite="lax"
        )
        return {"success": True, "token": token, "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
async def login_account(payload: LoginPayload, response: Response):
    """Authenticate username and password, returning session token and cookie."""
    user = auth.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = auth.create_session(user["id"])
    response.set_cookie(
        key="demoscene_session",
        value=token,
        max_age=30 * 86400,
        httponly=True,
        samesite="lax"
    )
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
    response.delete_cookie("demoscene_session")
    return {"success": True}


@app.get("/api/settings")
def get_settings():
    """Get current configuration status for IGDB API."""
    return boxart_service.get_igdb_status()


@app.post("/api/settings", dependencies=[Depends(verify_admin_key)])
def update_settings(payload: SettingsPayload):
    """Test and update IGDB API credentials, writing to .env."""
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
    offset: int = Query(0, ge=0)
):
    """Search and filter demo discs with pagination."""
    return db.search_demos(
        query=q,
        console=console,
        section_name=section,
        country=country,
        collection_status=status,
        limit=limit,
        offset=offset
    )


@app.get("/api/demos/{demo_id}")
def get_demo_detail(demo_id: str):
    """Retrieve full details of a specific demo disc, including games, scans, and intel."""
    demo = db.get_demo(demo_id)
    if not demo:
        raise HTTPException(status_code=404, detail="Demo disc not found")
    
    # Enrich game categories from cache (instant, non-blocking)
    demo["enriched_categories"] = game_intel.enrich_demo_contents(
        demo.get("categories", {}),
        console=demo.get("console", "PS2"),
        auto_fetch=False
    )
    return demo


@app.post("/api/collection/bulk", dependencies=[Depends(verify_admin_key)])
def bulk_update_collection_status(payload: BulkCollectionUpdate):
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
        variant_id=payload.variant_id
    )
    return {"success": True, "updated_count": updated_count}


@app.post("/api/collection/{demo_id}", dependencies=[Depends(verify_admin_key)])
def update_collection_status(demo_id: str, payload: CollectionUpdate):
    """Update collection tracking state for a demo disc/variant."""
    demo = db.get_demo(demo_id)
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
        notes=payload.notes or ""
    )
    return {"success": True, "record": result}


@app.get("/api/stats")
def get_collection_stats():
    """Retrieve collection statistics, counts, and completion rate."""
    return db.get_stats()


@app.get("/api/collection/games")
def get_collection_games():
    """Retrieve all unique games contained within owned demo discs."""
    return db.get_collection_games()


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


@app.get("/api/export", dependencies=[Depends(verify_admin_key)])
def export_backup():
    """Export complete collection data for JSON backup."""
    return db.export_collection_data()


@app.post("/api/import", dependencies=[Depends(verify_admin_key)])
def import_backup(payload: ImportPayload):
    """Import and merge JSON backup collection records."""
    count = db.import_collection_data(payload.dict())
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
    background_tasks.add_task(boxart_service.batch_fetch_boxart, limit=limit)
    return {"success": True, "message": f"Box art download queued for up to {limit} games."}


@app.get("/api/assets/pack/status")
def get_pack_status():
    """Check status of local assets and any active pack download task."""
    return asset_pack.get_asset_pack_status()


class AssetPackDownloadPayload(BaseModel):
    url: Optional[str] = None


@app.post("/api/assets/pack/download", dependencies=[Depends(verify_admin_key)])
def download_asset_pack(payload: Optional[AssetPackDownloadPayload] = None):
    """Trigger 1-click download & extraction of complete pre-packaged artwork bundle."""
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

