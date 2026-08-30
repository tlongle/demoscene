#!/usr/bin/env python3
"""
Starter script for PlayStation Demo Collector (DEMOSCENE).
Initializes database if needed and launches the web app.
"""
import os
import sys
import socket
import uvicorn

from app.core.config import settings
from app.core import database as db
from app.services import scraper


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
    settings.ensure_dirs()
    ip = get_local_ip()

    # Initialize DB & scrape if empty
    db.init_db()
    stats = db.get_stats()
    if stats["total_demos"] == 0:
        print("Initial database setup: scraping Crimson Ceremony archive...")
        scraper.run_scraper(verbose=True)

    print("\n" + "═" * 60)
    print("DEMOSCENE - PlayStation Demo Collector")
    print("═" * 60)
    print(f"Desktop:  http://localhost:{settings.PORT}")
    print(f"Mobile:   http://{ip}:{settings.PORT}")
    print("═" * 60 + "\n")

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=False)


if __name__ == "__main__":
    main()
