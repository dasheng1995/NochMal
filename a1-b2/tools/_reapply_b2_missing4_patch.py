"""Re-apply missing4 image statuses if repair overwrote words.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
WORK = ROOT / "_b2_pack_work"
PATCH = WORK / "_missing4_image_patch.json"
FILE_A = ROOT / "packs" / "image_search_queries_b2.json"


def main() -> None:
    if not PATCH.exists():
        raise SystemExit("no patch file")
    patch = json.loads(PATCH.read_text(encoding="utf-8"))
    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    file_a = json.loads(FILE_A.read_text(encoding="utf-8"))
    by_a = {it["word_id"]: it for it in file_a["items"]}
    n = 0
    for w in words:
        im = patch.get(w["id"])
        if not im:
            continue
        path = WORK / (im.get("path") or f"images/{w['id']}.webp")
        if not path.exists() or path.stat().st_size < 1500:
            print("missing file", path)
            continue
        w["image"] = im
        it = by_a.get(w["id"])
        if it:
            it["image_status"] = "ready"
            it["image_source"] = im.get("source") or ""
            if im.get("query_or_prompt"):
                it["search_en"] = im["query_or_prompt"]
        n += 1
    (WORK / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    FILE_A.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")
    ready = sum(1 for w in words if (w.get("image") or {}).get("status") == "ready")
    print(f"reapplied {n} ready={ready}/{len(words)}")


if __name__ == "__main__":
    main()
