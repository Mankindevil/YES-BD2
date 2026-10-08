"""Add costumes the official maintenance notice announces before souseha
lists them to the shipped character list (Leo 2026-10-07).

    python tools/fetch_official_costumes.py                    read the official site
    python tools/fetch_official_costumes.py --from-issue FILE  the notice text an issue carries

The logic is in src/tasks/fiend_hunt/official_notices.py.  The shipped tool
never reads the official site itself (Leo 2026-10-07); the list it reads is
the one this writes.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tasks.fiend_hunt import official_notices  # noqa: E402

OUT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "tasks"
    / "fiend_hunt"
    / "data"
    / "characters.json"
)


def main(args: list[str]) -> int:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    today = datetime.now(timezone.utc).date()
    if args[:1] == ["--from-issue"] and len(args) == 2:
        body = Path(args[1]).read_text(encoding="utf-8")
        found = official_notices.from_issue(data, body, today)
    elif not args:
        found = official_notices.find(data, today)
    else:
        print(__doc__)
        return 2
    by_id = {entry.get("id"): entry for entry in data.get("characters") or []}
    for character, costume in found:
        by_id[character].setdefault("costumes", []).append(costume)
    if found:
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"新增 {len(found)} 件服装")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
