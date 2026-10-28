"""Refresh data/heroes.json and data/heroicons/ from public sources (run after patches).

heroes.json: base attack range per hero (OpenDota constants).
heroicons/<key>.png: the small top-bar portraits (Steam CDN '<key>_sb.png'), used to
recognise which heroes are in the game from a screenshot.
"""
import json
from pathlib import Path

import requests

DATA = Path(__file__).with_name("data")
CDN = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes"
CDN_SB = "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/heroes"

raw = requests.get("https://api.opendota.com/api/constants/heroes", timeout=30).json()
heroes = {
    h["localized_name"]: {
        "id": h["id"],
        "key": h["name"].replace("npc_dota_hero_", ""),
        "min": h["base_attack_min"],
        "max": h["base_attack_max"],
        "type": h["attack_type"],
    }
    for h in raw.values()
}
DATA.mkdir(exist_ok=True)
(DATA / "heroes.json").write_text(json.dumps(heroes, ensure_ascii=False, indent=1), encoding="utf8")
print(f"{len(heroes)} heroes written")

icons = DATA / "heroicons"
icons.mkdir(exist_ok=True)
missing = []
for name, h in heroes.items():
    out = icons / f"{h['key']}.png"
    if out.exists():
        continue
    for url in (f"{CDN_SB}/{h['key']}_sb.png", f"{CDN}/{h['key']}.png"):
        r = requests.get(url, timeout=30)
        if r.ok and r.content[:4] == b"\x89PNG":
            out.write_bytes(r.content)
            break
    else:
        missing.append(name)
print(f"icons: {len(list(icons.glob('*.png')))} saved, missing: {missing}")
