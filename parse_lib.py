"""
Core parsing logic for demo pals (crimson-ceremony.net/demopals) entries.

The site groups content in blocks separated by blank lines:
  ## <Demo Title>
  ### <SCED code(s) / catalog number line>
  [Notes
   <notes text>]
  <Category name, e.g. "Playable">
  <game name>
  <game name>
  ...
  <Category name, e.g. "Trailer">
  <game name>
  ...
  - [thumbnail link/image]
  - [flag image]
  - [disc title text]
  - [thumbnail link/image]      <- next variant (disc release)
  - [flag image]
  - [disc title text]

This module works on *text already split into blank-line-separated blocks*.
The live scraper (scraper.py) turns real HTML into this same block shape,
so this logic is shared/reused rather than re-implemented.
"""
import re

KNOWN_CATEGORIES = {
    "Notes", "Playable", "Trailer", "Other", "EA sports video",
    "Multivideo", "Showreel", "GT3 Fest", "Saves",
    "Artwork & development", "Screenshots", "Sreenshots", "E3 video",
}

RE_THUMB_LINKED = re.compile(r"-\s*\[!\[thumbnail\]\(([^)]+)\)\]\(([^)]+)\)")
RE_THUMB_PLAIN = re.compile(r"-\s*!\[thumbnail\]\(([^)]+)\)")
RE_FLAG = re.compile(r"-\s*!\[([^\]]*)\]\(([^)]+)\)")
RE_SCED = re.compile(r"SCED-\d+[A-Za-z#]*")


def split_blocks(text: str):
    """Split on blank lines, drop empty blocks, keep internal line structure."""
    raw_blocks = re.split(r"\n\s*\n", text.strip())
    return [b.strip("\n") for b in raw_blocks if b.strip()]


def new_entry(series_name, series_slug):
    return {
        "series": series_name,
        "series_slug": series_slug,
        "title": None,
        "catalog_line": None,
        "sced_codes": [],
        "notes": "",
        "categories": {},
        "variants": [],
    }


def parse_variant_block(block: str):
    lines = [l.strip() for l in block.split("\n") if l.strip() != ""]
    # some rows render as "-" with nothing else -> keep as empty placeholders
    # pad in case flag/title lines are missing entirely
    while len(lines) < 3:
        lines.append("-")

    thumb_line, flag_line, title_line = lines[0], lines[1], lines[2]

    thumbnail = None
    detail_link = None
    m = RE_THUMB_LINKED.search(thumb_line)
    if m:
        thumbnail, detail_link = m.group(1), m.group(2)
    else:
        m = RE_THUMB_PLAIN.search(thumb_line)
        if m:
            thumbnail = m.group(1)

    country = ""
    flag_icon = ""
    m = RE_FLAG.search(flag_line)
    if m:
        country, flag_icon = m.group(1), m.group(2)

    disc_title = re.sub(r"^-\s*", "", title_line).strip()

    # try to pull an explicit SCED code out of the disc title line (some rows
    # repeat/override it, e.g. "...  SCED-52161 9679912")
    sced_in_title = RE_SCED.search(disc_title)

    # derive a stable variant id from the img= query param when present
    variant_id = None
    if detail_link and "img=" in detail_link:
        variant_id = detail_link.split("img=", 1)[1].split("#")[0]
    elif thumbnail:
        variant_id = thumbnail.rsplit("/", 1)[-1].rsplit(".", 1)[0]

    return {
        "variant_id": variant_id,
        "country": country,
        "flag_icon": flag_icon,
        "disc_title": disc_title,
        "thumbnail": thumbnail,
        "detail_link": detail_link,
        "sced_override": sced_in_title.group(0) if sced_in_title else None,
    }


def is_variant_block(block: str) -> bool:
    first_line = block.split("\n", 1)[0].strip()
    return first_line.startswith("- [") or first_line.startswith("- !")


def parse_page(text: str, series_name: str, series_slug: str):
    blocks = split_blocks(text)
    entries = []
    current = None
    current_category = None

    def flush():
        if current is not None:
            entries.append(current)

    for block in blocks:
        first_line = block.split("\n", 1)[0].strip()

        if first_line.startswith("## "):
            flush()
            current = new_entry(series_name, series_slug)
            current["title"] = first_line[3:].strip()
            current_category = None
            continue

        if current is None:
            # content before the first "## " heading (page intro text) -> skip
            continue

        if first_line.startswith("### "):
            current["catalog_line"] = first_line[4:].strip()
            current["sced_codes"] = RE_SCED.findall(current["catalog_line"])
            current_category = None
            continue

        if is_variant_block(block):
            current["variants"].append(parse_variant_block(block))
            current_category = None
            continue

        block_lines = [l for l in block.split("\n")]

        # The site glues a category label to its FIRST item with no blank
        # line between them (e.g. "Playable\nGame One" is a single block),
        # while later items in the same category each get their own block.
        # Detect and peel that off here.
        if block_lines[0].strip() in KNOWN_CATEGORIES:
            label = block_lines[0].strip()
            remainder = [l.strip() for l in block_lines[1:] if l.strip()]
            current_category = label
            if label == "Notes":
                current["notes"] = " ".join(remainder)
                current_category = None
            else:
                cat = "Screenshots" if label == "Sreenshots" else label
                for item in remainder:
                    current["categories"].setdefault(cat, []).append(item)
            continue

        # plain text block: continuation game name for the active category
        if current_category and current_category != "Notes":
            cat = "Screenshots" if current_category == "Sreenshots" else current_category
            current["categories"].setdefault(cat, []).append(block.strip())
        # else: stray text with no active category -> ignore

    flush()
    return entries


def make_demo_id(entry):
    sced = entry["sced_codes"][0] if entry["sced_codes"] else "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", entry["title"].lower()).strip("-")
    return f"{entry['series_slug']}__{slug}__{sced}"
