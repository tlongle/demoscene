"""
Redump.org Disc Preservation Integration for DEMOSCENE.
Allows live searching, querying, and 1-click importing of PS1 & PS2 demo discs from Redump.
"""
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

from app.core.database import create_manual_demo, get_demo

REDUMP_BASE = "http://redump.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DEMOSCENE/2.0 (PlayStation Demo Collector)"
}


def slugify_query(q: str) -> str:
    """Convert search string to Redump quicksearch slug format."""
    # Redump uses hyphen-separated lowercase words
    slug = re.sub(r"[^\w\s\-]", "", q.lower()).strip()
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug


def search_redump(query: str, system_filter: Optional[str] = None, timeout: int = 12) -> List[Dict[str, Any]]:
    """
    Search Redump.org discs by title or serial code.
    Returns structured list of matches for PS1 and PS2.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    # Handle direct SCED / serial searches
    slug = slugify_query(clean_q)
    url = f"{REDUMP_BASE}/discs/quicksearch/{slug}/"

    try:
        res = requests.get(url, headers=HEADERS, timeout=timeout)
        if res.status_code != 200:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        results = []
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 7:
                continue

            # Check disc detail link
            link = tr.find("a")
            href = link.get("href", "") if link else ""
            disc_id_match = re.search(r"/disc/(\d+)/", href)
            disc_id = int(disc_id_match.group(1)) if disc_id_match else None

            # Extract fields
            if link:
                span_sub = link.find("span", class_="small")
                if span_sub:
                    span_sub.decompose()
                title = link.get_text(" ", strip=True)
            else:
                title = tds[1].get_text(" ", strip=True)
            sys_raw = tds[2].get_text(strip=True).upper()
            version = tds[3].get_text(strip=True)
            edition = tds[4].get_text(strip=True)
            languages = tds[5].get_text(strip=True)
            serial = tds[6].get_text(strip=True).replace("\xa0", " ").strip()

            # Normalize system: PSX -> PS1, PS2 -> PS2
            console = "PS1" if sys_raw in ("PSX", "PS1", "PLAYSTATION") else ("PS2" if sys_raw == "PS2" else sys_raw)

            # Only retain PlayStation platforms
            if console not in ("PS1", "PS2"):
                continue

            if system_filter:
                f_norm = "PS1" if system_filter.upper() in ("PS1", "PSX") else system_filter.upper()
                if console != f_norm:
                    continue

            results.append({
                "redump_id": disc_id,
                "title": title,
                "console": console,
                "serial": serial,
                "version": version,
                "edition": edition,
                "languages": languages,
                "redump_url": f"{REDUMP_BASE}/disc/{disc_id}/" if disc_id else url
            })

        return results
    except Exception as e:
        print(f"⚠️ Redump search error: {e}")
        return []


def get_redump_disc(redump_id: int, timeout: int = 12) -> Optional[Dict[str, Any]]:
    """Fetch extended disc metadata from a Redump disc page."""
    url = f"{REDUMP_BASE}/disc/{redump_id}/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=timeout)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        details = {
            "redump_id": redump_id,
            "redump_url": url
        }

        # Main title is in h1
        h1 = soup.find("h1")
        if h1:
            details["title"] = h1.get_text(strip=True)

        for tr in soup.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                key = th.get_text(strip=True).lower()
                val = td.get_text(strip=True)
                if key == "system":
                    sys_upper = val.upper()
                    details["console"] = "PS1" if "PLAYSTATION 2" not in sys_upper and ("PSX" in sys_upper or "PLAYSTATION" in sys_upper) else "PS2"
                elif key == "serial":
                    details["serial"] = val
                elif key == "category":
                    details["category"] = val
                elif key == "region":
                    details["region"] = val
                elif key == "languages":
                    details["languages"] = val
                elif key == "media":
                    details["media"] = val
                elif key == "version":
                    details["version"] = val

        return details
    except Exception as e:
        print(f"⚠️ Error fetching Redump disc #{redump_id}: {e}")
        return None


def import_redump_disc(
    redump_id: int,
    custom_title: Optional[str] = None,
    playable_games: Optional[List[str]] = None,
    notes: Optional[str] = None,
    db_path: str = None
) -> Dict[str, Any]:
    """Import a Redump disc entry into DEMOSCENE master catalog."""
    disc_data = get_redump_disc(redump_id)
    if not disc_data:
        raise ValueError(f"Could not retrieve Redump disc #{redump_id}")

    title = custom_title or disc_data.get("title", f"Redump Demo #{redump_id}")
    console = disc_data.get("console", "PS2")
    serial = disc_data.get("serial", "").strip()
    region = disc_data.get("region", "Europe")
    sced_codes = [serial] if serial else []

    games = playable_games or []
    if not games:
        # Default with disc title itself as playable
        clean_name = re.sub(r"(?i)\s+(?:demo|sampler|special edition demo)\b.*", "", title).strip()
        games = [clean_name or title]

    categories = {"Playable": games}

    record_data = {
        "title": title,
        "console": console,
        "section_name": "Redump Archive",
        "section_group": "Redump Community",
        "section_url": disc_data["redump_url"],
        "sced_codes": sced_codes,
        "country": region,
        "categories": categories,
        "notes": notes or f"Imported from Redump.org (ID: {redump_id})",
        "source": "redump",
        "redump_id": redump_id,
        "primary_thumbnail": f"/assets/demopals/placeholder_{console.lower()}.png"
    }

    return create_manual_demo(record_data, db_path=db_path)
