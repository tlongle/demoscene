"""
Game Intel & Box Art Provider for PlayStation Demo Collector.
Enriches games with official/open box art, retro PlayStation packaging aesthetics,
and quick intel links (YouTube gameplay, MobyGames, Wikipedia, PSX Datacenter).
"""
import re
from urllib.parse import quote_plus
from typing import Dict, Any, List

import boxart_service

GENRE_KEYWORDS = {
    "racing": ["racing", "rally", "gt", "gran turismo", "wrc", "burnout", "formula", "moto", "f1", "nascar", "colin mcrae", "toca", "extreme-g", "xg3", "speed", "riders", "super trucks", "le mans", "airblade"],
    "action": ["metal gear", "gta", "grand theft auto", "hitman", "splinter cell", "tomb raider", "maximo", "devil may cry", "resident evil", "silent hill", "project zero", "sly", "ratchet", "jak", "crash", "spyro", "ape escape", "syphon filter", "dino crisis", "zone of the enders", "ico"],
    "sports": ["fifa", "pes", "pro evolution", "football", "nba", "nhl", "madden", "tiger woods", "tennis", "tony hawk", "skater", "snowboard", "snooker", "rugby", "boxing", "fight night", "smackdown", "wwe", "wwf", "iss"],
    "fighting": ["tekken", "dead or alive", "street fighter", "virtua fighter", "mortal kombat", "bloody roar", "soul reaver", "soulcalibur", "dragon ball", "kessen", "dynasty warriors"],
    "rpg": ["final fantasy", "dragon quest", "kingdom hearts", "dark cloud", "baldur", "star ocean", "suikoden", "breath of fire", "shadow hearts", "arc: twilight", "summoner", "orphen"],
    "shooter": ["time crisis", "half-life", "conflict", "medal of honor", "red faction", "socom", "killzone", "black", "deus ex", "timesplitters", "quake", "doom", "dropship", "star wars"],
}

PALETTES = [
    {"bg": "linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)", "accent": "#00d2ff"},
    {"bg": "linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)", "accent": "#43cea2"},
    {"bg": "linear-gradient(135deg, #373b44 0%, #4286f4 100%)", "accent": "#a8c0ff"},
    {"bg": "linear-gradient(135deg, #232526 0%, #414345 100%)", "accent": "#f7971e"},
    {"bg": "linear-gradient(135deg, #141e30 0%, #243b55 100%)", "accent": "#00f2fe"},
    {"bg": "linear-gradient(135deg, #16222f 0%, #2c3e50 100%)", "accent": "#4ca1af"},
    {"bg": "linear-gradient(135deg, #2b5876 0%, #4e4376 100%)", "accent": "#ff6a88"},
]


def detect_genre(game_name: str) -> str:
    """Detect general game genre based on title keywords."""
    name_lower = game_name.lower()
    for genre, keywords in GENRE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return genre
    return "Action / Adventure"


def get_game_intel(game_name: str, console: str = "PS2", category: str = "Playable") -> Dict[str, Any]:
    """
    Generate box art resolution, intel links, and retro packaging badge.
    """
    clean_name = re.sub(r"\s+", " ", game_name).strip()
    encoded = quote_plus(f"{console} {clean_name}")
    raw_encoded = quote_plus(clean_name)

    # Check if item is a video / trailer / making-of / non-game extra
    is_media_extra = boxart_service.is_non_game_media(clean_name)

    # Box art resolution (IGDB / Wikipedia / open cache)
    boxart_info = boxart_service.resolve_game_boxart(clean_name, console=console, auto_fetch=True)

    # Palette for fallback badge
    hash_val = sum(ord(c) for c in clean_name)
    palette = PALETTES[hash_val % len(PALETTES)]
    genre = detect_genre(clean_name)

    # Direct search links
    links = {
        "youtube": f"https://www.youtube.com/results?search_query={encoded}+demo+gameplay" if not is_media_extra else f"https://www.youtube.com/results?search_query=PS2+{encoded}",
        "mobygames": f"https://www.mobygames.com/search/quick?q={raw_encoded}",
        "wikipedia": f"https://en.wikipedia.org/wiki/Special:Search?search={raw_encoded}+video+game",
        "psxdatacenter": "https://psxdatacenter.com/psx2/pal_list2.html" if console == "PS2" else "https://psxdatacenter.com/pal_list.html",
    }

    words = [w for w in clean_name.split() if w.isalnum()]
    initials = "".join(w[0] for w in words[:4]).upper() if words else "PS"

    return {
        "name": clean_name,
        "console": console,
        "category": category,
        "genre": genre if not is_media_extra else "Video / Media Extra",
        "is_media_extra": is_media_extra,
        "boxart_url": boxart_info.get("cover_url"),
        "initials": initials,
        "palette": palette,
        "links": links
    }


def enrich_demo_contents(categories: Dict[str, List[str]], console: str = "PS2") -> Dict[str, List[Dict[str, Any]]]:
    """
    Enrich all category games with box art, intel, and retro styling.
    """
    enriched = {}
    for cat_name, games in categories.items():
        enriched[cat_name] = [get_game_intel(game, console, cat_name) for game in games]
    return enriched
