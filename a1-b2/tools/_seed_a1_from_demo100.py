"""Seed A1 workdir images/zh from demo_a1_100.deword."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
WORK = ROOT / "_a1_pack_work"
PACK100 = ROOT / "packs" / "demo_a1_100.deword"
FILE_A = ROOT / "packs" / "image_search_queries_a1.json"
TMP = ROOT / "_tmp_demo100"


def main() -> None:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir()
    with zipfile.ZipFile(PACK100) as z:
        z.extractall(TMP)
    w100 = {w["id"]: w for w in json.loads((TMP / "words.json").read_text(encoding="utf-8"))}
    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    file_a = json.loads(FILE_A.read_text(encoding="utf-8"))
    by_id = {it["word_id"]: it for it in file_a["items"]}
    n = 0
    for w in words:
        src = w100.get(w["id"])
        if not src:
            continue
        im = src.get("image") or {}
        if im.get("status") != "ready":
            continue
        rel = im.get("path") or f"images/{w['id']}.webp"
        srcp = TMP / rel
        if not srcp.exists():
            continue
        dst = WORK / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(srcp, dst)
        w["image"] = dict(im)
        if src.get("def_zh"):
            w["def_zh"] = src["def_zh"]
        if src.get("example_zh"):
            w["example_zh"] = src["example_zh"]
        it = by_id.get(w["id"])
        if it:
            it["image_status"] = "ready"
            it["image_source"] = im.get("source") or "pixabay"
        n += 1
    (WORK / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    FILE_A.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(TMP)
    print(f"seeded {n}")


if __name__ == "__main__":
    main()
