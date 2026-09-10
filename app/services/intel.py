"""
Game Intel & Box Art Provider for PBPX.
Enriches games with official box art, retro PlayStation packaging aesthetics,
and quick intel links (YouTube gameplay, Wikipedia).
"""
import re
from urllib.parse import quote_plus
from typing import Dict, Any, List

from app.services.boxart import resolve_game_boxart

GENRE_KEYWORDS = {
    "racing": ["racing", "rally", "gt", "gran turismo", "wrc", "burnout", "formula", "moto", "f1", "nascar", "colin mcrae", "toca", "extreme-g", "xg3", "speed", "riders", "super trucks", "le mans", "airblade"],
    "action": ["metal gear", "gta", "grand theft auto", "hitman", "splinter cell", "tomb raider", "maximo", "devil may cry", "resident evil", "silent hill", "project zero", "sly", "ratchet", "jak", "crash", "spyro", "ape escape", "syphon filter", "dino crisis", "zone of the enders", "ico"],
    "sports": ["fifa", "pes", "pro evolution", "football", "nba", "nhl", "madden", "tiger woods", "tennis", "tony hawk", "skater", "snowboard", "snooker", "rugby", "boxing", "fight night", "smackdown", "wwe", "wwf", "iss"],
    "fighting": ["tekken", "dead or alive", "street fighter", "virtua fighter", "mortal kombat", "bloody roar", "soul reaver", "soulcalibur", "dragon ball", "kessen", "dynasty warriors"],
    "rpg": ["final fantasy", "dragon quest", "kingdom hearts", "dark cloud", "baldur", "star ocean", "suikoden", "breath of fire", "shadow hearts", "arc: twilight", "summoner", "orphen"],
    "shooter": ["time crisis", "half-life", "conflict", "medal of honor", "red faction", "socom", "killzone", "black", "deus ex", "timesplitters", "quake", "doom", "dropship", "star wars"],
}


def detect_genre(game_name: str) -> str:
    """Guess general game genre based on title keywords."""
    name_clean = game_name.lower()
    for genre, keywords in GENRE_KEYWORDS.items():
        if any(kw in name_clean for kw in keywords):
            return genre.upper()
    return "PLAYSTATION"


def get_game_intel(game_name: str, console: str = "PS2", auto_fetch: bool = False) -> Dict[str, Any]:
    """Retrieve full intel metadata, box art URL, and links for a specific game."""
    genre = detect_genre(game_name)
    art_info = resolve_game_boxart(game_name, console=console, auto_fetch=auto_fetch)
    q_encoded = quote_plus(f"{game_name} {console}")

    return {
        "name": game_name,
        "console": console,
        "genre": genre,
        "boxart_url": art_info.get("cover_url"),
        "art_type": art_info.get("type", "boxart"),
        "initials": "".join([w[0] for w in re.findall(r"[a-zA-Z0-9]+", game_name)])[:3].upper(),
        "links": {
            "youtube": f"https://www.youtube.com/results?search_query={q_encoded}+gameplay+psx",
            "wikipedia": f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(game_name + ' video game')}"
        }
    }


def enrich_demo_contents(categories: Dict[str, List[str]], console: str = "PS2", auto_fetch: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    """Enrich all game names inside category lists with full intel & box art."""
    return {
        cat_name: [get_game_intel(g, console=console, auto_fetch=auto_fetch) for g in game_list]
        for cat_name, game_list in categories.items()
    }
