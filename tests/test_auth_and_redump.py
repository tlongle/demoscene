"""
Tests for Username/Password Authentication, Master Catalog Admin, and Redump Integration.
"""
import base64
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import database as db
from app.core import auth
from app.services import redump
from app.services.scraper import differential_merge_demos

client = TestClient(app)


def test_auth_workflow_setup_login_and_logout():
    """Verify first-time setup, login, me profile, and logout flow."""
    # 1. Setup admin
    r_setup = client.post("/api/auth/setup", json={
        "username": "superadmin",
        "password": "masterpassword123"
    })
    assert r_setup.status_code == 200
    setup_data = r_setup.json()
    assert setup_data["success"] is True
    assert setup_data["user"]["username"] == "superadmin"
    token = setup_data["token"]
    assert token

    # 2. Duplicate setup should be rejected
    r_dup = client.post("/api/auth/setup", json={
        "username": "anotheradmin",
        "password": "pass"
    })
    assert r_dup.status_code == 400

    # 3. Check /api/auth/me with Bearer token
    r_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200
    me_data = r_me.json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["username"] == "superadmin"

    # 4. Login with invalid password
    r_bad_login = client.post("/api/auth/login", json={
        "username": "superadmin",
        "password": "wrongpassword"
    })
    assert r_bad_login.status_code == 401

    # 5. Login with correct password
    r_login = client.post("/api/auth/login", json={
        "username": "superadmin",
        "password": "masterpassword123"
    })
    assert r_login.status_code == 200
    login_data = r_login.json()
    assert login_data["success"] is True
    new_token = login_data["token"]
    assert new_token

    # 6. Logout
    r_logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {new_token}"})
    assert r_logout.status_code == 200

    # 7. Old token is now invalid
    r_me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert r_me_after.json()["authenticated"] is False


def test_manual_demo_creation_and_zero_photo_tolerance():
    """Verify creating a manual disc with zero photos works and sets placeholder art."""
    # Login as admin
    r_login = client.post("/api/auth/login", json={
        "username": "superadmin",
        "password": "masterpassword123"
    })
    token = r_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "title": "OPS2 Demo 54",
        "console": "PS2",
        "section_name": "OPS2M UK",
        "sced_codes": ["SCED-52945"],
        "country": "UK",
        "categories": {
            "Playable": ["Killzone", "Burnout 3"]
        },
        "notes": "Rare collection buy out"
    }

    r_create = client.post("/api/admin/demos", json=payload, headers=headers)
    assert r_create.status_code == 200
    demo = r_create.json()["demo"]
    assert demo["title"] == "OPS2 Demo 54"
    assert demo["console"] == "PS2"
    assert "SCED-52945" in demo["sced_codes"]
    assert demo["source"] == "manual"
    # Zero-photo placeholder must be set
    assert "placeholder_ps2.png" in demo["primary_thumbnail"]

    # Verify searchable in main search API
    r_search = client.get("/api/demos?q=Killzone")
    assert r_search.status_code == 200
    search_data = r_search.json()
    found = any(d["id"] == demo["id"] for d in search_data["results"])
    assert found is True


def test_upload_scan_to_demo():
    """Verify Base64 image upload attaches to demo and updates primary thumbnail."""
    r_login = client.post("/api/auth/login", json={
        "username": "superadmin",
        "password": "masterpassword123"
    })
    token = r_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create dummy 1x1 png in base64
    dummy_png_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    demo = db.create_manual_demo({
        "title": "Bonus Demo 08 (You)",
        "console": "PS2",
        "sced_codes": ["SCED-54101"],
        "section_name": "Bonus Demos",
        "source": "redump"
    })

    upload_payload = {
        "image_base64": dummy_png_b64,
        "filename": "bonus_08_front.png",
        "scan_type": "cover_front"
    }

    r_upload = client.post(f"/api/admin/demos/{demo['id']}/scans", json=upload_payload, headers=headers)
    assert r_upload.status_code == 200
    res_data = r_upload.json()
    assert res_data["success"] is True
    assert "/assets/demopals/custom/" in res_data["url"]

    # Updated demo must now feature the custom upload as primary thumbnail
    updated_demo = db.get_demo(demo["id"])
    assert "/assets/demopals/custom/" in updated_demo["primary_thumbnail"]


def test_redump_disc_import_and_scraper_shield():
    """Verify Redump disc import creates record and Crimson scraper does not clobber it."""
    r_login = client.post("/api/auth/login", json={
        "username": "superadmin",
        "password": "masterpassword123"
    })
    token = r_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Mock Redump disc
    redump_demo = db.create_manual_demo({
        "title": "Bonus Demo 11 (You)",
        "console": "PS2",
        "sced_codes": ["SCED-54101"],
        "section_name": "Redump Archive",
        "source": "redump",
        "redump_id": 51114,
        "notes": "Imported from Redump"
    })
    assert redump_demo["source"] == "redump"

    # Run differential merge with simulated scraped entries
    fake_scraped = [
        {
            "id": redump_demo["id"],
            "title": "CLOBBERED TITLE",
            "console": "PS2",
            "section_name": "Malicious Overwrite",
            "section_group": "None",
            "section_url": "",
            "sced_codes": ["SCED-99999"],
            "categories": {"Playable": ["Fake Game"]}
        }
    ]

    stats = differential_merge_demos(fake_scraped)
    assert stats["unchanged"] >= 1

    # Disc in database must still be the pristine Redump disc
    preserved_demo = db.get_demo(redump_demo["id"])
    assert preserved_demo["title"] == "Bonus Demo 11 (You)"
    assert preserved_demo["source"] == "redump"
    assert "SCED-54101" in preserved_demo["sced_codes"]


def test_public_registration_and_multiuser_isolation(monkeypatch):
    """Verify open registration in public mode and strictly isolated collections between users."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MODE", "public")

    # 1. Register User A
    r_reg_a = client.post("/api/auth/register", json={
        "username": "collector_alice",
        "password": "alicepassword123"
    })
    assert r_reg_a.status_code == 200
    token_a = r_reg_a.json()["token"]
    user_a = r_reg_a.json()["user"]
    assert user_a["username"] == "collector_alice"
    assert user_a["is_admin"] is False  # Subsequent users are non-admin

    # 2. Register User B
    r_reg_b = client.post("/api/auth/register", json={
        "username": "collector_bob",
        "password": "bobpassword123"
    })
    assert r_reg_b.status_code == 200
    token_b = r_reg_b.json()["token"]
    user_b = r_reg_b.json()["user"]
    assert user_b["username"] == "collector_bob"

    # 3. Alice adds disc 1 to her collection
    r_all_demos = client.get("/api/demos?limit=2")
    demos = r_all_demos.json()["results"]
    demo_1_id = demos[0]["id"]
    demo_2_id = demos[1]["id"]

    r_add_a = client.post(
        f"/api/collection/{demo_1_id}",
        json={"status": "owned", "condition": "mint"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert r_add_a.status_code == 200

    # 4. Bob adds disc 2 to his collection
    r_add_b = client.post(
        f"/api/collection/{demo_2_id}",
        json={"status": "owned", "condition": "poor"},
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert r_add_b.status_code == 200

    # 5. Alice's collection check
    stats_a = client.get("/api/stats", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert stats_a["owned_demos"] == 1
    assert stats_a["conditions"]["mint"] == 1

    alice_detail_demo1 = client.get(f"/api/demos/{demo_1_id}", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert "default" in alice_detail_demo1["collection"]
    assert alice_detail_demo1["collection"]["default"]["status"] == "owned"

    alice_detail_demo2 = client.get(f"/api/demos/{demo_2_id}", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert "default" not in alice_detail_demo2["collection"]

    # 6. Bob's collection check
    stats_b = client.get("/api/stats", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert stats_b["owned_demos"] == 1
    assert stats_b["conditions"]["poor"] == 1

    bob_detail_demo2 = client.get(f"/api/demos/{demo_2_id}", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert bob_detail_demo2["collection"]["default"]["status"] == "owned"

    bob_detail_demo1 = client.get(f"/api/demos/{demo_1_id}", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert "default" not in bob_detail_demo1["collection"]

    # 7. Unauthenticated guest check in public mode
    guest_stats = client.get("/api/stats").json()
    assert guest_stats["owned_demos"] == 0

    guest_demo1 = client.get(f"/api/demos/{demo_1_id}").json()
    assert guest_demo1["collection"] == {}

    # 8. Non-admin cannot access admin catalog mutations
    r_hack_demo = client.post("/api/admin/demos", json={"title": "Hacked Demo"}, headers={"Authorization": f"Bearer {token_a}"})
    assert r_hack_demo.status_code == 401


def test_public_profile_showcase_and_privacy():
    """Verify public showcase URL /api/users/{username}/collection and privacy toggling."""
    # Login as alice
    r_login = client.post("/api/auth/login", json={"username": "collector_alice", "password": "alicepassword123"})
    token = r_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. View public profile as guest
    r_showcase = client.get("/api/users/collector_alice/collection")
    assert r_showcase.status_code == 200
    showcase_data = r_showcase.json()
    assert showcase_data["username"] == "collector_alice"
    assert showcase_data["is_private"] is False
    assert showcase_data["total_owned"] == 1
    assert len(showcase_data["discs"]) == 1

    # 2. Toggle privacy to private
    r_privacy = client.post("/api/auth/privacy", json={"is_private": True}, headers=headers)
    assert r_privacy.status_code == 200
    assert r_privacy.json()["is_private"] is True

    # 3. Guest (with cleared cookies) visiting private showcase gets hidden collection
    client.cookies.clear()
    r_guest_priv = client.get("/api/users/collector_alice/collection")
    assert r_guest_priv.status_code == 200
    priv_data = r_guest_priv.json()
    assert priv_data["is_private"] is True
    assert "private" in priv_data["message"]
    assert "discs" not in priv_data

    # 4. Alice herself visiting her own showcase can still view it
    r_owner_priv = client.get("/api/users/collector_alice/collection", headers=headers)
    assert r_owner_priv.status_code == 200
    owner_data = r_owner_priv.json()
    assert owner_data["is_private"] is False
    assert owner_data["total_owned"] == 1


def test_security_headers_and_auth_rate_limiting():
    """Verify security headers are attached and auth rate limiter prevents brute-force."""
    # 1. Verify standard security headers
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    # 2. Rate limiter triggers after exceeding threshold (15 attempts/min)
    hit_limit = False
    for i in range(20):
        r_lim = client.post("/api/auth/login", json={"username": f"attacker_{i}", "password": "bad"}, headers={"X-Forwarded-For": "198.51.100.1"})
        if r_lim.status_code == 429:
            hit_limit = True
            break
    assert hit_limit, "Rate limiter should return 429 after exceeding limit"


def test_public_mode_image_pulling_disabled_and_no_api_key_required():
    """Verify image pulling via UI is exclusive to self-hosted, and users need zero API keys."""
    from app.core.config import settings
    orig_mode = settings.MODE
    try:
        settings.MODE = "public"

        # Login as admin to verify that even an admin is prevented from UI image pulling in public mode
        r_login = client.post("/api/auth/login", json={"username": "superadmin", "password": "masterpassword123"})
        token = r_login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Image pulling endpoints return 403 in public mode
        r_pack = client.post("/api/assets/pack/download", json={}, headers=headers)
        assert r_pack.status_code == 403
        assert "disabled in public web mode" in r_pack.json()["detail"]

        r_boxart = client.post("/api/boxart/fetch-all", headers=headers)
        assert r_boxart.status_code == 403
        assert "unavailable in public web mode" in r_boxart.json()["detail"]

        r_twitch = client.post("/api/settings", json={"twitch_client_id": "id", "twitch_client_secret": "sec"}, headers=headers)
        assert r_twitch.status_code == 403
        assert "public web mode" in r_twitch.json()["detail"]

        # 2. Asset pack status always reports assets_ready=True in public mode
        r_status = client.get("/api/assets/pack/status")
        assert r_status.status_code == 200
        assert r_status.json()["assets_ready"] is True

        # 3. Standard users can track collection with zero API keys
        r_login_user = client.post("/api/auth/login", json={"username": "collector_alice", "password": "alicepassword123"})
        alice_token = r_login_user.json()["token"]
        r_all_demos = client.get("/api/demos?limit=1")
        demo_id = r_all_demos.json()["results"][0]["id"]
        # Notice: NO X-API-Key header provided!
        r_coll = client.post(f"/api/collection/{demo_id}", json={"status": "owned"}, headers={"Authorization": f"Bearer {alice_token}"})
        assert r_coll.status_code == 200
    finally:
        settings.MODE = orig_mode


def test_collector_profile_customization_and_metadata():
    """Verify collector profile customization endpoint, auth protection, and public showcase metadata."""
    # 1. Updating profile without auth fails with 401
    r_unauth = client.post("/api/auth/profile", json={"bio": "Test bio", "avatar": "disc"})
    assert r_unauth.status_code == 401

    # 2. Login as collector_alice
    r_login = client.post("/api/auth/login", json={"username": "collector_alice", "password": "alicepassword123"})
    assert r_login.status_code == 200
    token = r_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Update profile with custom bio, avatar, and favorite console
    r_update = client.post("/api/auth/profile", json={
        "bio": "Preserving rare PAL demo discs and Net Yaroze oddities.",
        "avatar": "net_yaroze",
        "favorite_console": "PS1"
    }, headers=headers)
    assert r_update.status_code == 200
    res_data = r_update.json()
    assert res_data["success"] is True
    assert res_data["user"]["bio"] == "Preserving rare PAL demo discs and Net Yaroze oddities."
    assert res_data["user"]["avatar"] == "net_yaroze"
    assert res_data["user"]["favorite_console"] == "PS1"

    # 4. Verify /api/auth/me returns updated profile fields
    r_me = client.get("/api/auth/me", headers=headers)
    assert r_me.status_code == 200
    me_data = r_me.json()
    assert me_data["user"]["bio"] == "Preserving rare PAL demo discs and Net Yaroze oddities."
    assert me_data["user"]["avatar"] == "net_yaroze"
    assert me_data["user"]["favorite_console"] == "PS1"

    # 5. Set collection back to public
    r_priv = client.post("/api/auth/privacy", json={"is_private": False}, headers=headers)
    assert r_priv.status_code == 200

    # 6. Guest visits public showcase and sees customized metadata
    client.cookies.clear()
    r_showcase = client.get("/api/users/collector_alice/collection")
    assert r_showcase.status_code == 200
    showcase = r_showcase.json()
    assert showcase["username"] == "collector_alice"
    assert showcase["bio"] == "Preserving rare PAL demo discs and Net Yaroze oddities."
    assert showcase["avatar"] == "net_yaroze"
    assert showcase["favorite_console"] == "PS1"
    assert showcase["is_admin"] is False
    assert showcase["created_at"] is not None


def test_production_hardening_security_and_health(monkeypatch):
    """Verify Phase 1 hardening: /api/health probe, 8-char password enforcement, session purge, proxy trust."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MODE", "public")

    # 1. Verify /api/health endpoint
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    health_data = r_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["app"] == "pbpx"
    assert health_data["version"] == "2.1.0"
    assert health_data["database"] == "connected"
    assert health_data["total_demos"] > 0

    # 2. Verify password policy rejects short and whitespace-only passwords
    r_short = client.post("/api/auth/register", json={
        "username": "short_pw_user",
        "password": "1234"
    })
    assert r_short.status_code == 400
    assert "at least 8 characters" in r_short.json()["detail"]

    r_spaces = client.post("/api/auth/register", json={
        "username": "space_pw_user",
        "password": "        "
    })
    assert r_spaces.status_code == 400
    assert "at least 8 characters" in r_spaces.json()["detail"]

    # 3. Verify session cleanup purges expired tokens
    from app.core import auth as auth_mod
    import app.core.database as db_mod
    conn = db_mod.get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_sessions (token, user_id, created_at, expires_at)
        VALUES ('expired_test_token_123', 1, datetime('now', '-2 days'), datetime('now', '-1 days'))
    """)
    conn.commit()
    conn.close()

    purged = auth_mod.cleanup_expired_sessions()
    assert purged >= 1

    # Ensure expired token is gone
    conn = db_mod.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM user_sessions WHERE token = 'expired_test_token_123'")
    assert cur.fetchone()[0] == 0
    conn.close()

    # 4. Verify rate limiter trusted proxy logic
    from app.main import is_trusted_proxy
    assert is_trusted_proxy("127.0.0.1") is True
    assert is_trusted_proxy("::1") is True
    assert is_trusted_proxy("localhost") is True
    assert is_trusted_proxy("testclient") is True
    assert is_trusted_proxy("172.18.0.1") is True
    assert is_trusted_proxy("10.0.0.15") is True
    assert is_trusted_proxy("203.0.113.195") is False
    assert is_trusted_proxy("198.51.100.22") is False

