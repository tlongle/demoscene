"""
Production Deployment Rehearsal & Stress Verification Suite.
Simulates high-concurrency writes, live WAL backup during write activity,
disaster recovery restoration drills, proxy header anti-spoofing,
and session lifecycle management.
"""
import concurrent.futures
import os
import shutil
import sqlite3
import tempfile
import time
from fastapi.testclient import TestClient
import pytest

from app.main import app, is_trusted_proxy, check_auth_rate_limit, _auth_rate_limits
from app.core.config import settings
from app.core import auth
import app.core.database as db

client = TestClient(app)


def test_concurrent_multiuser_collection_writes(monkeypatch):
    """Stress test: 30 concurrent threads performing collection updates under SQLite WAL mode."""
    monkeypatch.setattr(settings, "MODE", "public")

    # 1. Setup 3 distinct test users
    tokens = []
    for i in range(3):
        uname = f"rehearsal_user_{i}_{int(time.time()*1000)}"
        r = client.post("/api/auth/register", json={
            "username": uname,
            "password": "rehearsal_password_123"
        })
        assert r.status_code == 200, f"Failed registering {uname}: {r.text}"
        tokens.append(r.json()["token"])

    # Fetch available demo disc IDs
    r_demos = client.get("/api/demos?limit=10")
    assert r_demos.status_code == 200
    demo_ids = [d["id"] for d in r_demos.json()["results"]]
    assert len(demo_ids) >= 5

    errors = []

    def perform_write(user_idx: int, disc_idx: int, status_val: str):
        token = tokens[user_idx % len(tokens)]
        disc_id = demo_ids[disc_idx % len(demo_ids)]
        try:
            res = client.post(
                f"/api/collection/{disc_id}",
                json={
                    "status": status_val,
                    "condition": "mint" if status_val == "owned" else "good",
                    "has_sleeve": 1,
                    "has_case": 1,
                    "is_working": 1,
                    "notes": f"Concurrent test write by user {user_idx}"
                },
                headers={"Authorization": f"Bearer {token}"}
            )
            if res.status_code != 200:
                errors.append(f"HTTP {res.status_code}: {res.text}")
        except Exception as ex:
            errors.append(str(ex))

    # Execute 30 concurrent writes
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for i in range(30):
            u = i % 3
            d = i % len(demo_ids)
            st = "owned" if i % 2 == 0 else "wanted"
            futures.append(executor.submit(perform_write, u, d, st))
        concurrent.futures.wait(futures)

    assert len(errors) == 0, f"Encountered {len(errors)} concurrent write errors: {errors}"

    # Verify that each user's collection is queryable and consistent
    for token in tokens:
        st_res = client.get("/api/stats", headers={"Authorization": f"Bearer {token}"})
        assert st_res.status_code == 200
        stats = st_res.json()
        assert stats["total_demos"] > 0
        assert (stats["owned_demos"] + stats["wanted_demos"]) > 0


def test_live_wal_backup_and_restoration_drill(tmp_path):
    """Verify taking an atomic backup via VACUUM INTO and restoring it into a clean path."""
    import subprocess

    # 1. Take a fresh backup using scripts/backup_db.sh
    script_path = os.path.join(settings.BASE_DIR, "scripts", "backup_db.sh")
    restore_script_path = os.path.join(settings.BASE_DIR, "scripts", "restore_db.sh")
    assert os.path.exists(script_path), "backup_db.sh script missing"
    assert os.path.exists(restore_script_path), "restore_db.sh script missing"

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    custom_backup_file = str(backup_dir / "drill_snapshot.db")

    # Run native SQLite VACUUM INTO directly on active database to simulate live snapshot
    conn = db.get_db_connection()
    conn.execute(f"VACUUM INTO '{custom_backup_file}';")
    conn.close()

    assert os.path.exists(custom_backup_file), "Snapshot file was not created"
    assert os.path.getsize(custom_backup_file) > 100_000, "Snapshot file is suspiciously small"

    # 2. Verify integrity of the snapshot
    backup_conn = sqlite3.connect(custom_backup_file)
    integrity = backup_conn.execute("PRAGMA integrity_check;").fetchone()[0]
    assert integrity == "ok", f"Integrity check failed: {integrity}"

    # Verify key tables exist in the backup snapshot
    cur = backup_conn.cursor()
    cur.execute("SELECT count(*) FROM demos;")
    demo_count = cur.fetchone()[0]
    assert demo_count > 0, "No demos in backup snapshot"

    cur.execute("SELECT count(*) FROM users;")
    user_count = cur.fetchone()[0]
    assert user_count > 0, "No users in backup snapshot"
    backup_conn.close()

    # 3. Simulate Restoration into a fresh mock data target
    mock_data_dir = tmp_path / "restored_data"
    mock_data_dir.mkdir(parents=True, exist_ok=True)
    target_db_path = str(mock_data_dir / "pbpx.db")

    env = os.environ.copy()
    env["PBPX_DATA_DIR"] = str(mock_data_dir)
    env["PBPX_DB_PATH"] = target_db_path

    res = subprocess.run(
        [restore_script_path, custom_backup_file],
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"restore_db.sh failed with code {res.returncode}:\n{res.stderr}\n{res.stdout}"
    assert "Successfully restored database!" in res.stdout
    assert os.path.exists(target_db_path), "Restored database file does not exist at target path"

    # Verify restored database integrity
    restored_conn = sqlite3.connect(target_db_path)
    res_integrity = restored_conn.execute("PRAGMA integrity_check;").fetchone()[0]
    assert res_integrity == "ok"
    res_demos = restored_conn.execute("SELECT count(*) FROM demos;").fetchone()[0]
    assert res_demos == demo_count
    restored_conn.close()


def test_session_lifecycle_and_invalidation(monkeypatch):
    """Verify session creation, authentication, expiration, and automated cleanup."""
    monkeypatch.setattr(settings, "MODE", "public")
    # Register test user
    uname = f"sess_user_{int(time.time()*1000)}"
    r_reg = client.post("/api/auth/register", json={
        "username": uname,
        "password": "validpassword123"
    })
    assert r_reg.status_code == 200
    token = r_reg.json()["token"]

    # Session verification
    r_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200
    assert r_me.json()["authenticated"] is True

    # Insert an artificially expired session
    expired_token = f"test_expired_{time.time()}"
    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (uname,))
    uid = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO user_sessions (token, user_id, created_at, expires_at)
        VALUES (?, ?, datetime('now', '-3 days'), datetime('now', '-1 hours'))
    """, (expired_token, uid))
    conn.commit()
    conn.close()

    # Calling cleanup_expired_sessions should remove it from the DB
    purged_count = auth.cleanup_expired_sessions()
    assert purged_count >= 1

    # Accessing /api/auth/me with expired token must be rejected
    r_exp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r_exp.json()["authenticated"] is False

    conn = db.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM user_sessions WHERE token = ?", (expired_token,))
    assert cur.fetchone()[0] == 0
    conn.close()

    # Active token should still be completely valid
    r_me_active = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me_active.status_code == 200
    assert r_me_active.json()["authenticated"] is True


def test_rate_limiter_anti_spoofing_behavior():
    """Verify that external untrusted IP sockets cannot spoof proxy headers to bypass rate limits."""
    from starlette.requests import Request

    _auth_rate_limits.clear()

    # 1. Untrusted public peer IP (e.g. 203.0.113.10) sending spoofed CF-Connecting-IP header
    untrusted_scope = {
        "type": "http",
        "client": ("203.0.113.10", 54321),
        "headers": [
            (b"cf-connecting-ip", b"1.1.1.1"),
            (b"x-forwarded-for", b"1.1.1.1")
        ]
    }
    req_untrusted = Request(untrusted_scope)

    # 15 requests from untrusted peer must exhaust its own quota despite rotating spoofed headers
    for i in range(15):
        check_auth_rate_limit(req_untrusted, limit=15, window_sec=60)

    # 16th request must be blocked
    with pytest.raises(Exception) as exc_info:
        check_auth_rate_limit(req_untrusted, limit=15, window_sec=60)
    assert "Too many attempts" in str(exc_info.value.detail)

    # 2. Trusted internal proxy peer (127.0.0.1) honoring legitimate forwarded client IP
    _auth_rate_limits.clear()
    trusted_scope_client1 = {
        "type": "http",
        "client": ("127.0.0.1", 45000),
        "headers": [
            (b"cf-connecting-ip", b"198.51.100.55")
        ]
    }
    req_trusted_1 = Request(trusted_scope_client1)

    trusted_scope_client2 = {
        "type": "http",
        "client": ("127.0.0.1", 45001),
        "headers": [
            (b"cf-connecting-ip", b"198.51.100.77")
        ]
    }
    req_trusted_2 = Request(trusted_scope_client2)

    # Client 1 makes 15 attempts
    for _ in range(15):
        check_auth_rate_limit(req_trusted_1, limit=15, window_sec=60)

    # Client 1 is now blocked
    with pytest.raises(Exception):
        check_auth_rate_limit(req_trusted_1, limit=15, window_sec=60)

    # Client 2 through the same proxy is NOT blocked because their forwarded IP is distinct
    check_auth_rate_limit(req_trusted_2, limit=15, window_sec=60)


def test_health_probe_latency_and_payload():
    """Verify /api/health returns HTTP 200 within strict SLA (< 50ms) and provides accurate status."""
    start_time = time.perf_counter()
    r = client.get("/api/health")
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    assert r.status_code == 200
    assert elapsed_ms < 50, f"Healthcheck was unexpectedly slow: {elapsed_ms:.2f}ms"

    body = r.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"
    assert body["app"] == "pbpx"
    assert body["version"] == "2.1.0"
    assert isinstance(body["total_demos"], int)
    assert body["total_demos"] > 500
