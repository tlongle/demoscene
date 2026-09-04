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
