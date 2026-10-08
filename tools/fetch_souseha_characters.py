"""Refresh src/tasks/fiend_hunt/data/characters.json from souseha's BD2DB.

    python tools/fetch_souseha_characters.py

Leo allowed using https://browndust2-db.souseha.com for character and
costume names.  The site has no JSON endpoint for them: they ship inside
its JS modules (db-characters-<hash>.js, db-summons-<hash>.js), whose
names change with every deploy.  This script follows the page to them
(index -> main-*.js -> loadCharacters-*/loadSummons-*.js -> db-*.js),
lets node evaluate the modules, and keeps ids and names (繁中, 简中,
English, 日本語, 한국어) of characters, their costumes and summons, each
costume's skill name, SP costs and 爆发 costs, and each costume's portrait
(data/costumes/<id>.webp, 256 px as souseha serves them; Leo 2026-10-06: a built-in character
list, skills picked by the costume's picture).  Dev tool only: the shipped
tool reads the saved files and never goes online.  Needs node and OpenCV.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tasks.fiend_hunt import character_pool  # noqa: E402

SITE = "https://browndust2-db.souseha.com"
DATA = Path(__file__).resolve().parents[1] / "src" / "tasks" / "fiend_hunt" / "data"
OUT = DATA / "characters.json"
PORTRAITS = DATA / "costumes"
IMAGES = "https://image-bd2db.souseha.com/characters/{}.webp"
SUMMON_IMAGES = "https://image-bd2db.souseha.com/summons/{}.webp"
ELEMENTS = {"火": "fire", "水": "water", "風": "wind", "光": "light", "暗": "dark"}
PORTRAIT_SIZE = 256  # souseha's own size: sharp at 200 % screen scaling (Leo 2026-10-06)

NODE_DUMP = """
const chars = await import(process.argv[2]);
const summons = await import(process.argv[3]);
// loadCharacters: data = b, characters_i18n = c, costumes_i18n = a (see loadCharacters-*.js)
// loadSummons: data = s, i18n = a
console.log(JSON.stringify({
  base: chars.b, characters: chars.c, costumes: chars.a,
  summons: summons.s, summons_i18n: summons.a,
}));
"""


def get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "bd2-auto character snapshot"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def get(url: str) -> str:
    return get_bytes(url).decode("utf-8")


def asset(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    if match is None:
        raise SystemExit(f"souseha changed its pages: {pattern!r} not found")
    return match.group(1)


def download_modules(folder: Path) -> tuple[Path, Path]:
    main = asset(get(f"{SITE}/"), r'src="/assets/(main-[\w-]+\.js)"')
    main_js = get(f"{SITE}/assets/{main}")
    load_characters = get(f"{SITE}/assets/" + asset(main_js, r'"\./(loadCharacters-[\w-]+\.js)"'))
    load_summons = get(f"{SITE}/assets/" + asset(main_js, r'"\./(loadSummons-[\w-]+\.js)"'))
    paths = []
    for loader, name in ((load_characters, "characters"), (load_summons, "summons")):
        module = asset(loader, r'"\./(db-' + name + r'-[\w-]+\.js)"')
        path = folder / f"{name}.mjs"
        path.write_text(get(f"{SITE}/assets/{module}"), encoding="utf-8")
        paths.append(path)
    return paths[0], paths[1]


def snapshot(raw: dict) -> dict:
    characters = []
    for base in raw["base"]:
        cid = base["characterId"]
        names = raw["characters"].get(cid, {})
        costumes = []
        for costume in base.get("costumes") or []:
            info = raw["costumes"].get(costume["costumeId"], {})
            bursts = costume.get("burst") or []
            costumes.append(
                {
                    "id": costume["costumeId"],
                    "name_zh_tw": info.get("costumeName") or costume.get("costumeName", ""),
                    "name_zh_cn": info.get("costumeName_CN", ""),
                    "name_en": info.get("costumeName_en", ""),
                    "name_ja": info.get("costumeName_ja", ""),
                    "name_ko": info.get("costumeName_ko", ""),
                    "skill_zh_tw": info.get("skillName") or costume.get("skillName", ""),
                    "skill_zh_cn": info.get("skillName_CN", ""),
                    "skill_en": info.get("skillName_en", ""),
                    "skill_ja": info.get("skillName_ja", ""),
                    "skill_ko": info.get("skillName_ko", ""),
                    # SP by skill level (souseha's possibleSPList), 爆发 SP by level
                    "sp": [int(value) for value in costume.get("possibleSPList") or []],
                    "burst_sp": [int(entry.get("spCost", 0)) for entry in bursts if entry],
                }
            )
        characters.append(
            {
                "id": cid,
                # for the team editor's filters (Leo 2026-10-06, like souseha's)
                "star": int(base.get("star") or 0),
                "element": ELEMENTS.get(base.get("attribute", ""), ""),
                "costume": f"{cid}_{base.get('originalCostumeCode') or 1}",
                "name_zh_tw": names.get("character") or base.get("character", ""),
                "name_zh_cn": names.get("character_CN", ""),
                "name_en": names.get("character_en") or base.get("enName", ""),
                "name_ja": names.get("character_ja", ""),
                "name_ko": names.get("character_ko", ""),
                "costumes": costumes,
            }
        )
    summons = []
    for summon in raw["summons"]:
        names = raw["summons_i18n"].get(summon["summonId"], {})
        summons.append(
            {
                "id": summon["summonId"],
                "name_zh_tw": names.get("name") or summon.get("name", ""),
                "name_zh_cn": names.get("name_CN", ""),
                "name_en": names.get("name_en") or summon.get("enName", ""),
                "summoner_id": summon.get("characterId", ""),
                "costume_id": summon.get("costumeId", ""),
            }
        )
    return {
        "source": SITE,
        "fetched": date.today().isoformat(),
        "note": "names, skills and SP; portraits in costumes/; refresh with tools/fetch_souseha_characters.py",
        "characters": characters,
        "summons": summons,
    }


def _side(path: Path) -> int:
    import cv2
    import numpy as np

    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    return 0 if image is None else image.shape[1]


def save_portraits(data: dict) -> list[str]:
    """Each costume's and summon's portrait beside the JSON; the ids without one."""
    import cv2
    import numpy as np

    PORTRAITS.mkdir(parents=True, exist_ok=True)
    missing = []
    pictures = [
        (costume["id"], IMAGES)
        for character in data["characters"]
        for costume in character["costumes"]
        if not costume.get("temporary")  # official notice only, no picture yet
    ] + [(summon["id"], SUMMON_IMAGES) for summon in data["summons"]]
    for picture_id, source in pictures:
        path = PORTRAITS / f"{picture_id}.webp"
        if path.exists() and _side(path) == PORTRAIT_SIZE:
            continue
        try:
            raw = get_bytes(source.format(picture_id))
        except OSError:
            missing.append(picture_id)
            continue
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
        if image is None:
            missing.append(picture_id)
            continue
        image = cv2.resize(image, (PORTRAIT_SIZE, PORTRAIT_SIZE), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".webp", image, [cv2.IMWRITE_WEBP_QUALITY, 85])
        if ok:
            path.write_bytes(encoded.tobytes())
    return missing


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        characters, summons = download_modules(folder)
        script = folder / "dump.mjs"
        script.write_text(NODE_DUMP, encoding="utf-8")
        result = subprocess.run(
            ["node", str(script), characters.as_uri(), summons.as_uri()],
            capture_output=True,
            check=True,
            encoding="utf-8",
        )
    data = snapshot(json.loads(result.stdout))
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    # first-seen dates, costumes only the official notice has so far, and
    # the ids souseha's entries replaced (character_pool.py, Leo 2026-10-07)
    for line in character_pool.merge_souseha(old, data, date.today()):
        print(f"暂时的服装换成攻略网的：{line}")
    unchanged = {key: value for key, value in old.items() if key != "fetched"} == {
        key: value for key, value in data.items() if key != "fetched"
    }
    if not unchanged:  # no new commit every day just for the date
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    missing = save_portraits(data)
    if missing:
        print(f"no portrait for {', '.join(missing)}")
    costumes = sum(len(entry["costumes"]) for entry in data["characters"])
    counts = f"{len(data['characters'])} characters, {costumes} costumes"
    print(f"{OUT}: {counts}, {len(data['summons'])} summons")


if __name__ == "__main__":
    sys.exit(main())
