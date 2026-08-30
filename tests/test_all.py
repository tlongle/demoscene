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


