"""
Database management for SCENE.
Handles SQLite storage for scraped demo discs and user collection state.
"""
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("DEMOPALS_DB_PATH", "data/demopals.db")
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize database tables and indexes."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # Demos table
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

    # Custom game cover cache
    cur.execute("""
    CREATE TABLE IF NOT EXISTS game_covers (
        game_name TEXT PRIMARY KEY,
        cover_url TEXT NOT NULL,
        source TEXT DEFAULT 'auto',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Indexes for lightning-fast search
    cur.execute("CREATE INDEX IF NOT EXISTS idx_demos_console ON demos(console)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_demos_section ON demos(section_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_demos_title ON demos(title)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_collection_status ON collection(status)")

    conn.commit()
    conn.close()


def save_demo(demo_data: Dict[str, Any], db_path: str = DB_PATH) -> None:
    """Insert or update a scraped demo entry."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # Extract all game names for quick index search
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


def save_demos_bulk(demos_list: List[Dict[str, Any]], db_path: str = DB_PATH) -> int:
    """Bulk insert/update demos."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    for demo_data in demos_list:
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
    return len(demos_list)


def get_demo(demo_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
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
    demo["categories"] = json.loads(demo["contents_json"] or "{}")
    demo["variants"] = json.loads(demo["variants_json"] or "[]")

    # Get collection status for all variants of this demo
    cur.execute("SELECT * FROM collection WHERE demo_id = ?", (demo_id,))
    coll_rows = cur.fetchall()
    collection_map = {}
    for r in coll_rows:
        collection_map[r["variant_id"]] = dict(r)

    demo["collection"] = collection_map
    conn.close()
    return demo


def search_demos(
    query: str = "",
    console: Optional[str] = None,
    section_name: Optional[str] = None,
    country: Optional[str] = None,
    collection_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db_path: str = DB_PATH
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
        where_clauses.append("d.variants_json LIKE ?")
        params.append(f'%"country": "{country}"%')

    # Collection filter join
    join_clause = "LEFT JOIN collection c ON d.id = c.demo_id"
    if collection_status and collection_status != "ALL":
        if collection_status == "unowned":
            where_clauses.append("(c.status IS NULL OR c.status = 'unowned')")
        else:
            where_clauses.append("c.status = ?")
            params.append(collection_status)

    where_sql = " AND ".join(where_clauses)

    # Get total count
    count_sql = f"SELECT COUNT(DISTINCT d.id) FROM demos d {join_clause} WHERE {where_sql}"
    cur.execute(count_sql, params)
    total = cur.fetchone()[0]

    # Get page results
    query_sql = f"""
        SELECT DISTINCT d.*, 
               c.status as coll_status, 
               c.condition as coll_condition, 
               c.notes as coll_notes
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
        item["categories"] = json.loads(item["contents_json"] or "{}")
        item["variants"] = json.loads(item["variants_json"] or "[]")
        item["playable_count"] = len(item["categories"].get("Playable", []))
        item["trailer_count"] = len(item["categories"].get("Trailer", []))
        item["total_items"] = sum(len(v) for v in item["categories"].values())
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
    db_path: str = DB_PATH
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


def get_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Calculate collection statistics."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM demos")
    total_demos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM demos WHERE console = 'PS1'")
    total_ps1 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM demos WHERE console = 'PS2'")
    total_ps2 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT demo_id) FROM collection WHERE status = 'owned'")
    owned_demos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT demo_id) FROM collection WHERE status = 'wanted'")
    wanted_demos = cur.fetchone()[0]

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
    return {
        "total_demos": total_demos,
        "total_ps1": total_ps1,
        "total_ps2": total_ps2,
        "owned_demos": owned_demos,
        "wanted_demos": wanted_demos,
        "completion_rate": round((owned_demos / total_demos * 100) if total_demos else 0, 1),
        "series_breakdown": series_breakdown
    }


def export_collection_data(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Export all collection records for backup."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM collection")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"version": 1, "collection": rows}


def import_collection_data(data: Dict[str, Any], db_path: str = DB_PATH) -> int:
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
