"""
FastAPI Server for PlayStation Demo Scene Collector.
Supports Docker containerization, Nginx reverse proxy, Cloudflare Tunnels, and local asset caching.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import socket
import os
import json

import db
import scraper
import game_intel
import download_assets
import boxart_service

ASSETS_DIR = os.environ.get("ASSETS_DIR", "data/assets")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(os.path.join(ASSETS_DIR, "demopals"), exist_ok=True)
os.makedirs(os.path.join(ASSETS_DIR, "boxart"), exist_ok=True)

app = FastAPI(
    title="SCENE",
    description="Track and archive PS1 & PS2 demo discs, disc scans, slipcases, and box art",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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


@app.get("/api/settings")
def get_settings():
    """Get current configuration status for IGDB API."""
    return boxart_service.get_igdb_status()


@app.post("/api/settings")
def update_settings(payload: SettingsPayload):
    """Test and update IGDB API credentials, writing to .env."""
    res = boxart_service.save_igdb_credentials(
        payload.twitch_client_id,
        payload.twitch_client_secret
    )
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to verify credentials"))
    return res


@app.on_event("startup")
def startup_event():
    """Initialize DB and trigger initial scrape if empty."""
    db.init_db()
    stats = db.get_stats()
    if stats["total_demos"] == 0:
        print("⚠️ No demo discs found in database. Running initial scrape...")
        scraper.run_scraper(verbose=True)


# Mount local assets for disc photos, slipcase scans, and box art
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


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
    
    # Enrich game categories with box art & intel links
    demo["enriched_categories"] = game_intel.enrich_demo_contents(
        demo.get("categories", {}),
        console=demo.get("console", "PS2")
    )
    return demo


@app.post("/api/collection/bulk")
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


@app.post("/api/collection/{demo_id}")
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


@app.get("/api/filters")
def get_filter_options():
    """Retrieve unique filter options (consoles, sections, countries)."""
    conn = db.get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT console FROM demos ORDER BY console")
    consoles = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT DISTINCT section_name, console FROM demos ORDER BY console, section_name")
    sections = [{"name": r[0], "console": r[1]} for r in cur.fetchall()]

    cur.execute("SELECT variants_json FROM demos")
    all_variants_rows = cur.fetchall()
    countries = set()
    for row in all_variants_rows:
        try:
            vars_list = json.loads(row[0] or "[]")
            for v in vars_list:
                if v.get("country"):
                    countries.add(v["country"])
        except Exception:
            pass

    conn.close()
    return {
        "consoles": consoles,
        "sections": sections,
        "countries": sorted(list(countries))
    }


@app.get("/api/export")
def export_collection():
    """Export user's collection data as JSON backup."""
    return db.export_collection_data()


@app.post("/api/import")
def import_collection(payload: ImportPayload):
    """Restore collection data from JSON backup."""
    count = db.import_collection_data(payload.dict())
    return {"success": True, "imported_records": count}


@app.post("/api/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    """Trigger background refresh scrape of Crimson Ceremony archive."""
    background_tasks.add_task(scraper.run_scraper, verbose=True)
    return {"success": True, "message": "Scraper task queued."}


@app.post("/api/assets/download-all")
def trigger_assets_download(background_tasks: BackgroundTasks):
    """Trigger offline download and caching of all disc photos and sleeve scans."""
    background_tasks.add_task(download_assets.download_all_demopals_assets, max_workers=8, verbose=True)
    return {"success": True, "message": "Offline scans download queued in background."}


@app.post("/api/boxart/fetch-all")
def trigger_boxart_fetch(background_tasks: BackgroundTasks, limit: int = 150):
    """Trigger batch resolution and download of game box art."""
    background_tasks.add_task(boxart_service.batch_fetch_boxart, limit=limit)
    return {"success": True, "message": f"Box art download queued for up to {limit} games."}


def get_local_ip() -> str:
    """Detect local LAN IP for phone mobile access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.get("/api/network-info")
def get_network_info(request: Request):
    """Get local IP, port, and forwarded host for pairing."""
    ip = get_local_ip()
    port = int(os.environ.get("PORT", 8000))
    host_header = request.headers.get("x-forwarded-host") or request.headers.get("host")
    proto = request.headers.get("x-forwarded-proto") or "http"
    public_url = f"{proto}://{host_header}" if host_header else f"http://{ip}:{port}"

    return {
        "local_ip": ip,
        "port": port,
        "mobile_url": public_url
    }


# Mount static files directory
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    local_ip = get_local_ip()
    port = int(os.environ.get("PORT", 8000))
    print(f"\n========================================================")
    print(f"🎮 PlayStation Demo Scene Collector Web App")
    print(f"========================================================")
    print(f"💻 Desktop: http://localhost:{port}")
    print(f"📱 Mobile:  http://{local_ip}:{port}")
    print(f"========================================================\n")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
