"""
Database management for DEMOSCENE.
Handles SQLite storage for scraped demo discs, assets, and user collection state.
"""
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

from app.core.config import settings


def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = settings.DB_PATH
    abs_path = os.path.abspath(db_path)
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    conn = sqlite3.connect(abs_path, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = None) -> None:
    """Initialize database tables and indexes."""
    if db_path is None:
        db_path = settings.DB_PATH
    abs_path = os.path.abspath(db_path)
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    conn = get_db_connection(abs_path)
    cur = conn.cursor()

    # Demos master table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS demos (
        id TEXT PRIMARY KEY,
        console TEXT NOT NULL,
        section_group TEXT NOT NULL,
        section_name TEXT NOT NULL,
        section_url TEXT NOT NULL,
        title TEXT NOT NULL,
        catalog_line TEXT,
        sced_codes_json TEXT,
        notes TEXT,
        contents_json TEXT,
        variants_json TEXT,
        primary_thumbnail TEXT,
        game_names_index TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # User collection tracking table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS collection (
        demo_id TEXT NOT NULL,
        variant_id TEXT NOT NULL DEFAULT 'default',
        status TEXT NOT NULL DEFAULT 'unowned', -- 'owned', 'wanted', 'unowned'
        condition TEXT DEFAULT 'good',          -- 'mint', 'good', 'acceptable', 'poor', 'disc_only'
        has_sleeve INTEGER DEFAULT 1,          -- 1 or 0
        has_case INTEGER DEFAULT 1,            -- 1 or 0
        is_working INTEGER DEFAULT 1,          -- 1 or 0
        notes TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (demo_id, variant_id),
        FOREIGN KEY (demo_id) REFERENCES demos(id) ON DELETE CASCADE
    )
    """)

    # Custom game cover cache table (composite primary key on console + game_name)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS game_covers (
        console TEXT NOT NULL DEFAULT 'PS2',
        game_name TEXT NOT NULL,
        cover_url TEXT NOT NULL,
        source TEXT DEFAULT 'auto',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (console, game_name)
    )
    """)

    # Check migration for game_covers composite PK
    cur.execute("PRAGMA table_info(game_covers)")
    cover_cols = [c["name"] for c in cur.fetchall()]
    if "console" not in cover_cols:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS game_covers_new (
            console TEXT NOT NULL DEFAULT 'PS2',
            game_name TEXT NOT NULL,
            cover_url TEXT NOT NULL,
            source TEXT DEFAULT 'auto',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (console, game_name)
        )
        """)
        cur.execute("INSERT OR REPLACE INTO game_covers_new (console, game_name, cover_url, source, updated_at) SELECT 'PS2', game_name, cover_url, source, updated_at FROM game_covers")
        cur.execute("DROP TABLE game_covers")
        cur.execute("ALTER TABLE game_covers_new RENAME TO game_covers")

    # Indexes for lightning-fast search
    cur.execute("CREATE INDEX IF NOT EXISTS idx_demos_console ON demos(console)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_demos_section ON demos(section_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_demos_title ON demos(title)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_collection_status ON collection(status)")

    # Migration for Dedicated Demos or single-game discs with empty contents_json
    cur.execute("SELECT id, title, section_name, contents_json FROM demos WHERE contents_json = '{}' OR contents_json IS NULL OR contents_json = ''")
    empty_rows = cur.fetchall()
    if empty_rows:
        for r in empty_rows:
            d_id, d_title, d_sec, _ = r
            cats = ensure_demo_categories(d_title, {}, d_sec)
            cats_json = json.dumps(cats)
            game_idx = " | ".join(cats.get("Playable", [])).lower()
            cur.execute("UPDATE demos SET contents_json = ?, game_names_index = ? WHERE id = ?", (cats_json, game_idx, d_id))

    # Normalize any remote crimson-ceremony thumbnail URLs to local asset paths
    cur.execute("""
    UPDATE demos 
    SET primary_thumbnail = REPLACE(primary_thumbnail, 'https://crimson-ceremony.net/demopals/', '/assets/demopals/')
    WHERE primary_thumbnail LIKE 'https://crimson-ceremony.net/demopals/%'
    """)
    cur.execute("""
    UPDATE demos 
    SET primary_thumbnail = REPLACE(primary_thumbnail, 'http://crimson-ceremony.net/demopals/', '/assets/demopals/')
    WHERE primary_thumbnail LIKE 'http://crimson-ceremony.net/demopals/%'
    """)

    conn.commit()
    conn.close()


def normalize_asset_url(url: Optional[str]) -> Optional[str]:
    """Convert remote Crimson Ceremony URLs to local /assets/demopals/ paths."""
    if not url or not isinstance(url, str):
        return url
    if "crimson-ceremony.net/demopals/" in url:
        return "/assets/demopals/" + url.split("demopals/", 1)[1]
    if "crimson-ceremony.net/f-" in url:
        return "/assets/demopals/" + url.split("crimson-ceremony.net/", 1)[1]
    return url


def ensure_demo_categories(demo_title: str, categories: Dict[str, List[str]], section_name: str = "") -> Dict[str, List[str]]:
    """
    Ensure dedicated demos or single-game discs have at least the game itself catalogued as Playable.
    """
    if not categories or not any(categories.values()):
        import re
        clean_title = re.sub(r"(?i)\s+(?:demo|sampler|special edition demo)\b", "", demo_title).strip()
        if not clean_title:
            clean_title = demo_title.strip()
        return {"Playable": [clean_title]}
    return categories


def resolve_demo_assets(demo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure primary_thumbnail and variant scans always prioritize local downloaded
    high-resolution Slipcase / Front Cover (-1.jpg) and High-Quality CD scan (-2.jpg).
    """
    section_url = demo.get("section_url", "")
    parts = [p for p in section_url.split("/") if p and p != "index.php"]
    subfolder = parts[-1] if parts else ""

    variants = demo.get("variants", [])
    primary_thumb = None

    for v in variants:
        img_key = v.get("img_key")
        flag_icon = v.get("flag_icon")

        if flag_icon:
            flag_filename = flag_icon.split("/")[-1]
            local_flag = os.path.join(settings.DEMOPALS_ASSETS_DIR, flag_filename)
            if os.path.exists(local_flag) and os.path.getsize(local_flag) > 0:
                v["flag_icon"] = f"/assets/demopals/{flag_filename}"

        scans = []
        if img_key and subfolder:
            folder_dir = os.path.join(settings.DEMOPALS_ASSETS_DIR, subfolder)
            remote_base = f"https://crimson-ceremony.net/demopals/{subfolder}/"

            # 1. Slipcase / Front Cover (-1.jpg)
            path_1 = os.path.join(folder_dir, f"{img_key}-1.jpg")
            if os.path.exists(path_1) and os.path.getsize(path_1) > 0:
                scans.append({
                    "type": "cover_front",
                    "label": "Slipcase / Cover Front",
                    "local_url": f"/assets/demopals/{subfolder}/{img_key}-1.jpg",
                    "remote_url": f"{remote_base}{img_key}-1.jpg"
                })
                if not primary_thumb:
                    primary_thumb = f"/assets/demopals/{subfolder}/{img_key}-1.jpg"
            else:
                if not primary_thumb:
                    primary_thumb = f"{remote_base}{img_key}-1.jpg"

            # 2. High-Quality CD Scan (-2.jpg)
            path_2 = os.path.join(folder_dir, f"{img_key}-2.jpg")
            if os.path.exists(path_2) and os.path.getsize(path_2) > 0:
                scans.append({
                    "type": "disc_scan",
                    "label": "High-Quality CD Scan",
                    "local_url": f"/assets/demopals/{subfolder}/{img_key}-2.jpg",
                    "remote_url": f"{remote_base}{img_key}-2.jpg"
                })
                if not primary_thumb:
                    primary_thumb = f"/assets/demopals/{subfolder}/{img_key}-2.jpg"
            elif not primary_thumb:
                primary_thumb = f"{remote_base}{img_key}-2.jpg"

            # 3. Extras (-3.jpg to -6.jpg)
            labels = {
                3: "Slipcase / Cover Back",
                4: "Inlay / Booklet Scan",
                5: "Alternate Scan",
                6: "Alternate Scan"
            }
            for i in range(3, 7):
                path_i = os.path.join(folder_dir, f"{img_key}-{i}.jpg")
                if os.path.exists(path_i) and os.path.getsize(path_i) > 0:
                    scans.append({
                        "type": "alternate_art",
                        "label": labels.get(i, f"Alternate Scan #{i}"),
                        "local_url": f"/assets/demopals/{subfolder}/{img_key}-{i}.jpg",
                        "remote_url": f"{remote_base}{img_key}-{i}.jpg"
                    })

            # 4. Low-Res thumbnail (-0.jpg) at the end as an extra
            path_0 = os.path.join(folder_dir, f"{img_key}-0.jpg")
            if os.path.exists(path_0) and os.path.getsize(path_0) > 0:
                scans.append({
                    "type": "thumb_overview",
                    "label": "Overview Thumbnail (Low-Res)",
                    "local_url": f"/assets/demopals/{subfolder}/{img_key}-0.jpg",
                    "remote_url": f"{remote_base}{img_key}-0.jpg"
                })

        if scans:
            v["scans"] = scans

    if primary_thumb:
        demo["primary_thumbnail"] = primary_thumb

    return demo


def save_demo(demo_data: Dict[str, Any], db_path: str = None) -> None:
    """Insert or update a scraped demo entry."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    all_games = []
    contents = demo_data.get("categories", {})
    for cat_games in contents.values():
        all_games.extend(cat_games)
    game_names_index = " | ".join(all_games).lower()

    cur.execute("""
    INSERT INTO demos (
        id, console, section_group, section_name, section_url,
        title, catalog_line, sced_codes_json, notes,
        contents_json, variants_json, primary_thumbnail,
        game_names_index, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(id) DO UPDATE SET
        console=excluded.console,
        section_group=excluded.section_group,
        section_name=excluded.section_name,
        section_url=excluded.section_url,
        title=excluded.title,
        catalog_line=excluded.catalog_line,
        sced_codes_json=excluded.sced_codes_json,
        notes=excluded.notes,
        contents_json=excluded.contents_json,
        variants_json=excluded.variants_json,
        primary_thumbnail=excluded.primary_thumbnail,
        game_names_index=excluded.game_names_index,
        updated_at=CURRENT_TIMESTAMP
    """, (
        demo_data["id"],
        demo_data["console"],
        demo_data["section_group"],
        demo_data["section_name"],
        demo_data["section_url"],
        demo_data["title"],
        demo_data.get("catalog_line", ""),
        json.dumps(demo_data.get("sced_codes", [])),
        demo_data.get("notes", ""),
        json.dumps(demo_data.get("categories", {})),
        json.dumps(demo_data.get("variants", [])),
        demo_data.get("primary_thumbnail", ""),
        game_names_index
    ))

    conn.commit()
    conn.close()


def save_demos_bulk(demos_list: List[Dict[str, Any]], db_path: str = None) -> int:
    """Bulk insert/update demos."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    for demo_data in demos_list:
        contents = ensure_demo_categories(demo_data["title"], demo_data.get("categories", {}), demo_data.get("section_name", ""))
        demo_data["categories"] = contents

        all_games = []
        for cat_games in contents.values():
            all_games.extend(cat_games)
        game_names_index = " | ".join(all_games).lower()

        cur.execute("""
        INSERT INTO demos (
            id, console, section_group, section_name, section_url,
            title, catalog_line, sced_codes_json, notes,
            contents_json, variants_json, primary_thumbnail,
            game_names_index, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            console=excluded.console,
            section_group=excluded.section_group,
            section_name=excluded.section_name,
            section_url=excluded.section_url,
            title=excluded.title,
            catalog_line=excluded.catalog_line,
            sced_codes_json=excluded.sced_codes_json,
            notes=excluded.notes,
            contents_json=excluded.contents_json,
            variants_json=excluded.variants_json,
            primary_thumbnail=excluded.primary_thumbnail,
            game_names_index=excluded.game_names_index,
            updated_at=CURRENT_TIMESTAMP
        """, (
            demo_data["id"],
            demo_data["console"],
            demo_data["section_group"],
            demo_data["section_name"],
            demo_data["section_url"],
            demo_data["title"],
            demo_data.get("catalog_line", ""),
            json.dumps(demo_data.get("sced_codes", [])),
            demo_data.get("notes", ""),
            json.dumps(contents),
            json.dumps(demo_data.get("variants", [])),
            demo_data.get("primary_thumbnail", ""),
            game_names_index
        ))

    conn.commit()
    conn.close()
    return len(demos_list)


def get_demo(demo_id: str, db_path: str = None) -> Optional[Dict[str, Any]]:
    """Retrieve full demo details by ID with collection status."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT * FROM demos WHERE id = ?", (demo_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    demo = dict(row)
    demo["sced_codes"] = json.loads(demo["sced_codes_json"] or "[]")
    raw_cats = json.loads(demo["contents_json"] or "{}")
    demo["categories"] = ensure_demo_categories(demo["title"], raw_cats, demo.get("section_name", ""))
    demo["variants"] = json.loads(demo["variants_json"] or "[]")

    cur.execute("SELECT * FROM collection WHERE demo_id = ?", (demo_id,))
    coll_rows = cur.fetchall()
    collection_map = {}
    for r in coll_rows:
        collection_map[r["variant_id"]] = dict(r)

    demo["collection"] = collection_map
    conn.close()
    return resolve_demo_assets(demo)


def search_demos(
    query: str = "",
    console: Optional[str] = None,
    section_name: Optional[str] = None,
    country: Optional[str] = None,
    collection_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db_path: str = None
) -> Dict[str, Any]:
    """Search and filter demos."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    params = []
    where_clauses = ["1=1"]

    if console and console.upper() != "ALL":
        where_clauses.append("d.console = ?")
        params.append(console.upper())

    if section_name and section_name != "ALL":
        where_clauses.append("d.section_name = ?")
        params.append(section_name)

    if query:
        q_clean = query.strip()
        q_param = f"%{q_clean}%"
        where_clauses.append("""
            (d.title LIKE ? 
             OR d.catalog_line LIKE ? 
             OR d.sced_codes_json LIKE ? 
             OR d.game_names_index LIKE ?
             OR d.variants_json LIKE ?)
        """)
        params.extend([q_param, q_param, q_param, q_param, q_param])

    if country and country != "ALL":
        where_clauses.append("EXISTS (SELECT 1 FROM json_each(d.variants_json) WHERE json_extract(value, '$.country') LIKE ?)")
        params.append(country)

    # Collection filter join
    join_clause = "LEFT JOIN collection c ON d.id = c.demo_id"
    if collection_status and collection_status != "ALL":
        if collection_status == "unowned":
            where_clauses.append("(c.status IS NULL OR c.status = 'unowned')")
        else:
            where_clauses.append("c.status = ?")
            params.append(collection_status)

    where_sql = " AND ".join(where_clauses)

    count_sql = f"SELECT COUNT(DISTINCT d.id) FROM demos d {join_clause} WHERE {where_sql}"
    cur.execute(count_sql, params)
    total = cur.fetchone()[0]

    query_sql = f"""
        SELECT DISTINCT d.*, 
               c.status as coll_status, 
               c.condition as coll_condition, 
               c.notes as coll_notes,
               c.has_sleeve as coll_has_sleeve,
               c.has_case as coll_has_case,
               c.is_working as coll_is_working
        FROM demos d
        {join_clause}
        WHERE {where_sql}
        ORDER BY 
            CASE d.console WHEN 'PS1' THEN 1 WHEN 'PS2' THEN 2 ELSE 3 END,
            d.section_name,
            d.title
        LIMIT ? OFFSET ?
    """
    cur.execute(query_sql, params + [limit, offset])
    rows = cur.fetchall()

    results = []
    for r in rows:
        item = dict(r)
        item["sced_codes"] = json.loads(item["sced_codes_json"] or "[]")
        raw_cats = json.loads(item["contents_json"] or "{}")
        item["categories"] = ensure_demo_categories(item["title"], raw_cats, item.get("section_name", ""))
        variants = json.loads(item["variants_json"] or "[]")
        for v in variants:
            if v.get("flag_icon"):
                v["flag_icon"] = normalize_asset_url(v["flag_icon"])
            if v.get("thumb_img"):
                v["thumb_img"] = normalize_asset_url(v["thumb_img"])
        item["variants"] = variants
        item["playable_count"] = len(item["categories"].get("Playable", []))
        item["trailer_count"] = len(item["categories"].get("Trailer", []))
        item["total_items"] = sum(len(v) for v in item["categories"].values())
        item["primary_thumbnail"] = normalize_asset_url(item.get("primary_thumbnail"))
        if not item.get("primary_thumbnail") and item["variants"]:
            item["primary_thumbnail"] = item["variants"][0].get("thumb_img") or "/assets/demopals/f-eur.jpg"
        results.append(item)

    conn.close()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": results
    }


def update_collection(
    demo_id: str,
    variant_id: str = "default",
    status: str = "owned",
    condition: str = "good",
    has_sleeve: int = 1,
    has_case: int = 1,
    is_working: int = 1,
    notes: str = "",
    db_path: str = None
) -> Dict[str, Any]:
    """Update or insert collection record for a demo/variant."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO collection (
        demo_id, variant_id, status, condition, has_sleeve, has_case, is_working, notes, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(demo_id, variant_id) DO UPDATE SET
        status=excluded.status,
        condition=excluded.condition,
        has_sleeve=excluded.has_sleeve,
        has_case=excluded.has_case,
        is_working=excluded.is_working,
        notes=excluded.notes,
        updated_at=CURRENT_TIMESTAMP
    """, (demo_id, variant_id, status, condition, has_sleeve, has_case, is_working, notes))

    conn.commit()
    conn.close()
    return {
        "demo_id": demo_id,
        "variant_id": variant_id,
        "status": status,
        "condition": condition,
        "has_sleeve": has_sleeve,
        "has_case": has_case,
        "is_working": is_working,
        "notes": notes
    }


def bulk_update_collection(
    demo_ids: List[str],
    updates: Dict[str, Any],
    variant_id: str = "default",
    db_path: str = None
) -> int:
    """
    Bulk update collection records for multiple demo discs.
    """
    if not demo_ids:
        return 0

    conn = get_db_connection(db_path)
    cur = conn.cursor()

    count = 0
    for did in demo_ids:
        cur.execute("SELECT * FROM collection WHERE demo_id = ? AND variant_id = ?", (did, variant_id))
        row = cur.fetchone()

        status = updates.get("status", row["status"] if row else "owned")
        condition = updates.get("condition", row["condition"] if row else "good")
        has_sleeve = updates.get("has_sleeve", row["has_sleeve"] if row else 1)
        has_case = updates.get("has_case", row["has_case"] if row else 1)
        is_working = updates.get("is_working", row["is_working"] if row else 1)
        notes = updates.get("notes", row["notes"] if row else "")

        cur.execute("""
        INSERT INTO collection (
            demo_id, variant_id, status, condition, has_sleeve, has_case, is_working, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(demo_id, variant_id) DO UPDATE SET
            status=excluded.status,
            condition=excluded.condition,
            has_sleeve=excluded.has_sleeve,
            has_case=excluded.has_case,
            is_working=excluded.is_working,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
        """, (did, variant_id, status, condition, has_sleeve, has_case, is_working, notes))
        count += 1

    conn.commit()
    conn.close()
    return count


def get_stats(db_path: str = None) -> Dict[str, Any]:
    """Calculate detailed collection statistics."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            COUNT(DISTINCT d.id) as total_demos,
            COUNT(DISTINCT CASE WHEN d.console = 'PS1' THEN d.id END) as total_ps1,
            COUNT(DISTINCT CASE WHEN d.console = 'PS2' THEN d.id END) as total_ps2,
            COUNT(DISTINCT CASE WHEN c.status = 'owned' THEN d.id END) as owned_demos,
            COUNT(DISTINCT CASE WHEN c.status = 'wanted' THEN d.id END) as wanted_demos,
            COUNT(DISTINCT CASE WHEN c.status = 'owned' AND d.console = 'PS1' THEN d.id END) as owned_ps1,
            COUNT(DISTINCT CASE WHEN c.status = 'owned' AND d.console = 'PS2' THEN d.id END) as owned_ps2,
            COUNT(DISTINCT CASE WHEN c.status = 'owned' AND c.has_sleeve = 1 THEN d.id END) as count_sleeve,
            COUNT(DISTINCT CASE WHEN c.status = 'owned' AND c.has_case = 1 THEN d.id END) as count_case,
            COUNT(DISTINCT CASE WHEN c.status = 'owned' AND c.is_working = 1 THEN d.id END) as count_working
        FROM demos d
        LEFT JOIN collection c ON d.id = c.demo_id
    """)
    totals = dict(cur.fetchone())

    cur.execute("""
        SELECT condition, COUNT(*) as count 
        FROM collection 
        WHERE status = 'owned' 
        GROUP BY condition
    """)
    cond_rows = dict(cur.fetchall())

    cur.execute("""
        SELECT d.console, d.section_name, COUNT(DISTINCT d.id) as total,
               COUNT(DISTINCT CASE WHEN c.status = 'owned' THEN d.id END) as owned,
               COUNT(DISTINCT CASE WHEN c.status = 'wanted' THEN d.id END) as wanted
        FROM demos d
        LEFT JOIN collection c ON d.id = c.demo_id
        GROUP BY d.console, d.section_name
        ORDER BY d.console, d.section_name
    """)
    series_breakdown = [dict(r) for r in cur.fetchall()]
    conn.close()

    total_demos = totals["total_demos"]
    owned_demos = totals["owned_demos"]

    return {
        "total_demos": total_demos,
        "total_ps1": totals["total_ps1"],
        "total_ps2": totals["total_ps2"],
        "owned_demos": owned_demos,
        "wanted_demos": totals["wanted_demos"],
        "owned_ps1": totals["owned_ps1"],
        "owned_ps2": totals["owned_ps2"],
        "completion_rate": round((owned_demos / total_demos * 100) if total_demos else 0, 1),
        "conditions": {
            "disc_only": cond_rows.get("disc_only", 0),
            "mint": cond_rows.get("mint", 0),
            "good": cond_rows.get("good", 0),
            "acceptable": cond_rows.get("acceptable", 0),
            "poor": cond_rows.get("poor", 0),
            "with_sleeve": totals["count_sleeve"],
            "in_case": totals["count_case"],
            "working": totals["count_working"]
        },
        "series_breakdown": series_breakdown
    }


def export_collection_data(db_path: str = None) -> Dict[str, Any]:
    """Export all collection records for backup."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM collection")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"version": 1, "collection": rows}


def import_collection_data(data: Dict[str, Any], db_path: str = None) -> int:
    """Import collection records from JSON backup."""
    records = data.get("collection", [])
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    count = 0
    for r in records:
        cur.execute("""
        INSERT INTO collection (
            demo_id, variant_id, status, condition, has_sleeve, has_case, is_working, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(demo_id, variant_id) DO UPDATE SET
            status=excluded.status,
            condition=excluded.condition,
            has_sleeve=excluded.has_sleeve,
            has_case=excluded.has_case,
            is_working=excluded.is_working,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
        """, (
            r["demo_id"],
            r.get("variant_id", "default"),
            r.get("status", "owned"),
            r.get("condition", "good"),
            r.get("has_sleeve", 1),
            r.get("has_case", 1),
            r.get("is_working", 1),
            r.get("notes", "")
        ))
        count += 1
    conn.commit()
    conn.close()
    return count


def get_collection_games(db_path: str = None) -> List[Dict[str, Any]]:
    """Retrieve all unique playable games contained within owned collection demo discs."""
    from app.services.intel import get_game_intel

    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.title, d.console, d.section_name, d.catalog_line, d.sced_codes_json, d.contents_json, d.primary_thumbnail
        FROM collection c
        JOIN demos d ON c.demo_id = d.id
        WHERE c.status = 'owned'
    """)
    rows = cur.fetchall()
    conn.close()

    games_map = {}
    for r in rows:
        demo_id = r["id"]
        demo_title = r["title"]
        console = r["console"]
        sec_name = r["section_name"]
        sceds = json.loads(r["sced_codes_json"] or "[]")
        sced_code = sceds[0] if sceds else (r["catalog_line"] or "")
        cats = ensure_demo_categories(demo_title, json.loads(r["contents_json"] or "{}"), sec_name)

        for cat_name, g_list in cats.items():
            # Only include Playable categories (skip Trailers, Videos, Saves, FMV, Notes, etc.)
            cat_lower = cat_name.strip().lower()
            if not (cat_lower.startswith("playable") or cat_lower == "net yaroze"):
                continue

            for g_name in g_list:
                clean_gname = g_name.strip()
                if not clean_gname:
                    continue
                key = f"{console}:{clean_gname.lower()}"
                if key not in games_map:
                    intel = get_game_intel(clean_gname, console=console)
                    games_map[key] = {
                        **intel,
                        "categories": [cat_name],
                        "found_in": [{
                            "demo_id": demo_id,
                            "demo_title": demo_title,
                            "sced": sced_code,
                            "section_name": sec_name,
                            "thumbnail": r["primary_thumbnail"]
                        }]
                    }
                else:
                    if cat_name not in games_map[key]["categories"]:
                        games_map[key]["categories"].append(cat_name)
                    if not any(f["demo_id"] == demo_id for f in games_map[key]["found_in"]):
                        games_map[key]["found_in"].append({
                            "demo_id": demo_id,
                            "demo_title": demo_title,
                            "sced": sced_code,
                            "section_name": sec_name,
                            "thumbnail": r["primary_thumbnail"]
                        })

    return sorted(list(games_map.values()), key=lambda x: x["name"].lower())
