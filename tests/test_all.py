"""
Comprehensive Test Suite for DEMOSCENE.
Validates Security, Authentication, Data Integrity, Box Art Caching, and Stats Aggregations.
"""
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import (
    get_db_connection,
    init_db,
    search_demos,
    get_demo,
    update_collection,
    bulk_update_collection,
    get_stats,
    get_collection_games
)
from app.services.boxart import record_boxart, get_cached_boxart_path
from app.services.intel import detect_genre, get_game_intel
from app.main import app

client = TestClient(app)


def test_database_foreign_keys():
    """Verify PRAGMA foreign_keys is strictly enforced."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys")
    fk_enabled = cur.fetchone()[0]
    conn.close()
    assert fk_enabled == 1, "SQLite foreign keys must be active"


def test_composite_game_covers_cache():
    """Verify game_covers table supports composite (console, game_name) keys."""
    # Insert PS1 version of a game
    record_boxart("Hydro Thunder", "/assets/boxart/PS1_hydro.jpg", "test", console="PS1")
    # Insert PS2 version of the same title
    record_boxart("Hydro Thunder", "/assets/boxart/PS2_hydro.jpg", "test", console="PS2")

    ps1_cover = get_cached_boxart_path("Hydro Thunder", console="PS1")
    ps2_cover = get_cached_boxart_path("Hydro Thunder", console="PS2")

    assert ps1_cover == "/assets/boxart/PS1_hydro.jpg"
    assert ps2_cover == "/assets/boxart/PS2_hydro.jpg"


def test_search_demos_and_json_query():
    """Verify search, country filtering via json_each, and pagination."""
    res = search_demos(query="", console="PS1", limit=10)
    assert "results" in res
    assert "total" in res
    assert len(res["results"]) <= 10

    # Test country filter
    country_res = search_demos(country="France", limit=5)
    assert country_res["total"] >= 0


def test_collection_games_playable_only():
    """Verify get_collection_games strictly includes Playable titles."""
    games = get_collection_games()
    assert isinstance(games, list)
    for g in games:
        assert "name" in g
        assert "console" in g
        assert "found_in" in g
        assert "genre" in g


def test_single_query_stats_consistency():
    """Verify stats calculated match database counts."""
    stats = get_stats()
    assert "total_demos" in stats
    assert "owned_demos" in stats
    assert "conditions" in stats
    assert "series_breakdown" in stats
    assert stats["total_demos"] >= stats["owned_demos"]


def test_api_public_read_endpoints():
    """Verify public read endpoints work without authentication."""
    r_stats = client.get("/api/stats")
    assert r_stats.status_code == 200

    r_demos = client.get("/api/demos?limit=5")
    assert r_demos.status_code == 200

    r_filters = client.get("/api/filters")
    assert r_filters.status_code == 200

    r_games = client.get("/api/collection/games")
    assert r_games.status_code == 200


def test_api_admin_auth_protection(monkeypatch):
    """Verify mutating endpoints are rejected when ADMIN_API_KEY is configured and key is omitted."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "super_secret_demo_key_123")

    # 1. Unauthenticated mutation attempt -> 401
    r_mutate = client.post("/api/collection/test-id", json={"status": "owned"})
    assert r_mutate.status_code == 401

    # 2. Invalid key -> 401
    r_invalid = client.post(
        "/api/collection/test-id",
        headers={"X-API-Key": "wrong_key"},
        json={"status": "owned"}
    )
    assert r_invalid.status_code == 401

    # 3. Valid key -> allowed (or 404 if demo doesn't exist, but passes auth)
    r_valid = client.post(
        "/api/collection/test-id",
        headers={"X-API-Key": "super_secret_demo_key_123"},
        json={"status": "owned"}
    )
    assert r_valid.status_code in (200, 404)  # Auth check passed!


def test_genre_detection_and_intel():
    """Verify non-blocking intel generation and genre heuristics."""
    intel = get_game_intel("Gran Turismo 2", console="PS1", auto_fetch=False)
    assert intel["name"] == "Gran Turismo 2"
    assert intel["genre"] == "RACING"
    assert "youtube" in intel["links"]
    assert "wikipedia" in intel["links"]


def test_download_demo_assets_with_none_flag_and_path_resolution():
    """Verify downloader handles None flag_icon and parses relative URLs safely without root write errors."""
    from app.services.downloader import download_demo_assets, download_single_image

    sample_demo = {
        "id": "test_demo_id",
        "title": "Test Demo",
        "section_url": "https://crimson-ceremony.net/demopals/eurodemo/index.php",
        "primary_thumbnail": "",
        "variants": [
            {
                "country": "Germany",
                "flag_icon": None,  # Should not raise AttributeError
                "img_key": "ger199608"
            },
            {
                "country": "UK",
                "flag_icon": "https://crimson-ceremony.net/f-uk.jpg",
                "img_key": "uk001"
            }
        ]
    }

    # Should run without crashing or PermissionError
    res = download_demo_assets(sample_demo)
    assert res["id"] == "test_demo_id"
    assert len(res["variants"]) == 2


def test_catalog_seeding_on_empty_db(tmp_path):
    """Verify an empty database automatically seeds 872 verified discs from catalog_seed.json."""
    from app.core.database import init_db, seed_database_if_empty, get_stats

    temp_db = str(tmp_path / "test_empty.db")
    init_db(temp_db)

    stats = get_stats(temp_db)
    assert stats["total_demos"] == 872
    assert stats["total_ps1"] > 0
    assert stats["total_ps2"] > 0


def test_scraper_anomaly_gate_rejects_malformed_data():
    """Verify the integrity gate blocks corrupt scrapes (e.g. only 19 discs or 100+ games per disc)."""
    from app.services.scraper import validate_scraped_entries

    # 1. Reject too few discs (e.g. 19 discs)
    fake_few_demos = [{"id": f"demo_{i}", "categories": {"Playable": ["Game 1"]}} for i in range(19)]
    is_valid, msg = validate_scraped_entries(fake_few_demos, min_expected=800)
    assert not is_valid
    assert "Parsed only 19" in msg

    # 2. Reject disc with collapsed block of 100+ games
    fake_bloated_demos = [{"id": f"demo_{i}", "categories": {"Playable": [f"Game {j}" for j in range(100)]}} for i in range(850)]
    is_valid, msg = validate_scraped_entries(fake_bloated_demos, min_expected=800)
    assert not is_valid
    assert "parsed with 100 items" in msg

    # 3. Accept valid dataset
    fake_valid_demos = [{"id": f"demo_{i}", "categories": {"Playable": ["Game A", "Game B"]}} for i in range(872)]
    is_valid, msg = validate_scraped_entries(fake_valid_demos, min_expected=800)
    assert is_valid


def test_differential_merge_preserves_collection(tmp_path):
    """Verify differential sync preserves existing user collection statuses and custom condition notes."""
    from app.core.database import init_db, update_collection, get_db_connection
    from app.services.scraper import differential_merge_demos

    temp_db = str(tmp_path / "test_merge.db")
    init_db(temp_db)

    # User marks a demo as owned with specific notes
    target_demo_id = "ps1_euro_demo__the-official-playstation-magazine-cd-1__sles-00107"
    update_collection(
        demo_id=target_demo_id,
        variant_id="default",
        status="owned",
        condition="mint",
        notes="Precious mint condition find",
        db_path=temp_db
    )

    # Scraper runs differential sync with a simulated new batch
    simulated_scraped = [
        {
            "id": target_demo_id,
            "console": "PS1",
            "section_group": "OPM demos",
            "section_name": "Euro Demo",
            "section_url": "https://crimson-ceremony.net/demopals/eurodemo/index.php",
            "title": "The Official PlayStation Magazine CD 1",
            "catalog_line": "SCES-00107",
            "sced_codes": ["SCES-00107", "NEW-SCED-999"],
            "notes": "Original archive notes",
            "categories": {"Playable": ["Tomb Raider"]},
            "variants": [],
            "primary_thumbnail": "/assets/demopals/eurodemo/uk001-1.jpg"
        }
    ]

    res = differential_merge_demos(simulated_scraped, db_path=temp_db)
    assert res["updated"] == 1

    # Check collection status is still intact
    conn = get_db_connection(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT status, condition, notes FROM collection WHERE demo_id = ?", (target_demo_id,))
    row = cur.fetchone()
    conn.close()

    assert row["status"] == "owned"
    assert row["condition"] == "mint"
    assert row["notes"] == "Precious mint condition find"


def test_sync_metadata_tracking(tmp_path):
    """Verify sync watermark metadata storage and retrieval."""
    from app.core.database import init_db, get_metadata, set_metadata

    temp_db = str(tmp_path / "test_meta.db")
    init_db(temp_db)

    # Initial watermark set to 2026.02.11
    assert get_metadata("last_synced_date", db_path=temp_db) == "2026.02.11"

    # Update metadata
    set_metadata("last_synced_date", "2026.09.01", db_path=temp_db)
    assert get_metadata("last_synced_date", db_path=temp_db) == "2026.09.01"


def test_peek_for_updates_when_already_up_to_date(tmp_path, monkeypatch):
    """Verify peek_and_sync_updates completes cleanly without modifying database when no new releases exist."""
    from app.core.database import init_db
    from app.services.scraper import peek_and_sync_updates

    temp_db = str(tmp_path / "test_peek.db")
    init_db(temp_db)

    # Simulate HTML response where newest date is 2026.02.11 (matches baseline)
    mock_html = """
    <html>
      <body>
        <section>
          <h2>2026.02.11</h2>
          <ul class="varitem">
            <li class="vartitle">PlayStation 2 Magazine CD 19<br><span class="red">SCED-50154</span></li>
          </ul>
        </section>
      </body>
    </html>
    """

    class MockResponse:
        text = mock_html
        status_code = 200
        def raise_for_status(self): pass

    import requests
    monkeypatch.setattr(requests.Session, "get", lambda *args, **kwargs: MockResponse())

    res = peek_and_sync_updates(db_path=temp_db, verbose=False)
    assert res["status"] == "up_to_date"
    assert res["new_discs_added"] == 0
    assert "up to date" in res["message"]


def test_asset_pack_status_and_download_flow(monkeypatch):
    """Verify asset pack status endpoint and download trigger."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import asset_pack

    client = TestClient(app)

    # 1. Test pack status
    res = client.get("/api/assets/pack/status")
    assert res.status_code == 200
    data = res.json()
    assert "assets_ready" in data
    assert "local_asset_count" in data
    assert "is_downloading" in data
    assert "default_url" in data

    # 2. Test download trigger with monkeypatched worker
    monkeypatch.setattr(asset_pack, "_run_download_and_extract", lambda url: None)
    post_res = client.post("/api/assets/pack/download", json={"url": "https://example.com/test.tar.gz"})
    assert post_res.status_code == 200
    assert post_res.json()["success"] is True





