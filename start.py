#!/usr/bin/env python3
"""
Starter script for PlayStation Demo Scene Collector (SCENE).
Initializes database if needed and launches the web app.
"""
import os
import sys
import socket
import uvicorn

import db
import scraper


def get_local_ip() -> str:
    """Detect LAN IP address for phone / tablet pairing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    port = int(os.environ.get("PORT", 8000))
    ip = get_local_ip()
    db_path = os.environ.get("DEMOPALS_DB_PATH", "data/demopals.db")
    assets_dir = os.environ.get("ASSETS_DIR", "data/assets")

    # Ensure all directories exist with write access
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    os.makedirs(os.path.join(assets_dir, "demopals"), exist_ok=True)
    os.makedirs(os.path.join(assets_dir, "boxart"), exist_ok=True)

    # Initialize DB & scrape if empty
    db.init_db(db_path)
    stats = db.get_stats(db_path)
    if stats["total_demos"] == 0:
        print("Initial database setup: scraping Crimson Ceremony archive...")
        scraper.run_scraper(db_path=db_path, verbose=True)

    print("\n" + "═" * 60)
    print("SCENE")
    print("═" * 60)
    print(f"Desktop:  http://localhost:{port}")
    print(f"Mobile:   http://{ip}:{port}")
    print("═" * 60 + "\n")

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
