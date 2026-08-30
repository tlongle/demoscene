"""
Core parsing logic for demo pals (crimson-ceremony.net/demopals) entries.
"""
import re
from typing import Dict, Any, List

KNOWN_CATEGORIES = {
    "Notes", "Playable", "Trailer", "Other", "EA sports video",
    "Net Yaroze", "Saves", "Video", "FMV", "Slide Show", "Rolling Demo"
}

SCED_PATTERN = re.compile(
    r"(?:SCED|SCES|SLED|SLES|PBPX|PAPX|SCDX|SLUS|SCUS|PSXC|SLKA|SLPM)-\d+[A-Za-z0-9#]*",
    re.IGNORECASE
)


def parse_block(block_text: str, default_console: str = "PS1") -> Dict[str, Any]:
    """Parse a single text block representing a demo disc entry."""
    lines = [line.strip() for line in block_text.strip().splitlines() if line.strip()]
    if not lines:
        return {}

    title = ""
    catalog_line = ""
    sced_codes = []
    notes = []
    categories: Dict[str, List[str]] = {}
    variants: List[Dict[str, Any]] = []

    current_cat = None
    in_notes = False

    # Extract disc title
    if lines and lines[0].startswith("## "):
        title = lines[0][3:].strip()
        lines = lines[1:]
    elif lines:
        title = lines[0]
        lines = lines[1:]

    # Extract catalog / SCED line
    if lines and (lines[0].startswith("### ") or "SCED" in lines[0] or "SLES" in lines[0] or "SCES" in lines[0] or "SLED" in lines[0]):
        catalog_line = lines[0].replace("###", "").strip()
        sced_codes = SCED_PATTERN.findall(catalog_line)
        lines = lines[1:]

    current_variant = {}

    for line in lines:
        # Notes block
        if line.startswith("[Notes") or line == "Notes":
            in_notes = True
            current_cat = None
            note_content = line.replace("[Notes", "").replace("]", "").strip()
            if note_content:
                notes.append(note_content)
            continue
        elif in_notes:
            if line.endswith("]"):
                in_notes = False
                note_content = line[:-1].strip()
                if note_content:
                    notes.append(note_content)
            elif any(line.startswith(cat) for cat in KNOWN_CATEGORIES) or line.startswith("- "):
                in_notes = False
            else:
                notes.append(line)
                continue

        # Check for category header
        is_cat_header = False
        for cat in KNOWN_CATEGORIES:
            if line.lower() == cat.lower() or line.lower().startswith(cat.lower() + " ("):
                current_cat = cat
                if current_cat not in categories:
                    categories[current_cat] = []
                is_cat_header = True
                break

        if is_cat_header:
            continue

        # Check for variant line (- ...)
        if line.startswith("- "):
            item = line[2:].strip()
            if not current_variant:
                current_variant = {"disc_title": title, "country": "Europe", "sced": "", "img_key": ""}

            if item.lower().endswith((".jpg", ".png", ".gif")):
                if "f-" in item:
                    current_variant["flag_icon"] = item
                    country = item.split("f-")[-1].split(".")[0]
                    if country:
                        current_variant["country"] = country.upper()
                else:
                    current_variant["thumb_img"] = item
                    key = item.split("-")[0] if "-" in item else item.split(".")[0]
                    if key:
                        current_variant["img_key"] = key
            else:
                current_variant["disc_title"] = item
                sceds_in_item = SCED_PATTERN.findall(item)
                if sceds_in_item:
                    current_variant["sced"] = sceds_in_item[0]
                    sced_codes.extend(sceds_in_item)

            if "thumb_img" in current_variant and "disc_title" in current_variant:
                variants.append(current_variant)
                current_variant = {}
            continue

        # Item within category
        if current_cat:
            categories[current_cat].append(line)

    if current_variant:
        variants.append(current_variant)

    if not sced_codes and catalog_line:
        sced_codes = SCED_PATTERN.findall(catalog_line)

    return {
        "title": title,
        "catalog_line": catalog_line,
        "sced_codes": list(dict.fromkeys(sced_codes)),
        "notes": "\n".join(notes).strip(),
        "categories": categories,
        "variants": variants
    }
