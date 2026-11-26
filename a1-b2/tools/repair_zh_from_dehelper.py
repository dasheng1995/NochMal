"""Repair def_zh in a .deword pack using local Dehelper dictionary."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

import dehelper_lookup as dh

ROOT = Path(r"e:\local_project\deutsch\a1-b2")


def looks_chinese(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--also-copy", type=Path, action="append", default=[])
    args = ap.parse_args()

    pack: Path = args.pack
    work: Path = args.work
    work.mkdir(parents=True, exist_ok=True)

    if not (work / "words.json").exists():
        with zipfile.ZipFile(pack, "r") as zf:
            zf.extractall(work)

    words = json.loads((work / "words.json").read_text(encoding="utf-8"))
    print(f"loading dict {dh.DIC} …", flush=True)
    data = dh.DIC.read_bytes()
    print(f"dict {len(data)/1024/1024:.1f}MB words={len(words)}", flush=True)

    changed = 0
    found = 0
    missing = []
    for i, w in enumerate(words, 1):
        lemma = w.get("lemma") or ""
        pos = w.get("pos") or ""
        hits = dh.lookup(lemma, data=data, pos=pos)
        if not hits:
            missing.append(lemma)
        else:
            found += 1
            new_zh = hits[0]["def_zh_short"] or hits[0]["def_zh"]
            # keep a readable short form with顿号
            new_zh = new_zh.replace(",", "、").replace("，", "、")
            new_zh = re.sub(r"、+", "、", new_zh).strip("、")
            if w.get("def_zh") != new_zh:
                w["def_zh"] = new_zh
                w["def_zh_source"] = "dehelper"
                changed += 1
        if i % 100 == 0 or i == len(words):
            print(f"  lookup [{i}/{len(words)}] hit={found} changed={changed}", flush=True)

    print(f"words={len(words)} dehelper_hit={found} changed={changed} missing={len(missing)}", flush=True)
    if missing[:10]:
        print("missing sample:", missing[:10], flush=True)

    print("writing words.json …", flush=True)
    (work / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest_path = work / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {}
    manifest["zh_def_source"] = "dehelper"
    manifest["zh_def_hit"] = f"{found}/{len(words)}"
    manifest["content_hash"] = hashlib.sha256((work / "words.json").read_bytes()).hexdigest()[:16]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("repacking deword (may take a few minutes) …", flush=True)
    if pack.exists():
        pack.unlink()
    with zipfile.ZipFile(pack, "w", zipfile.ZIP_DEFLATED) as zf:
        files = [p for p in work.rglob("*") if p.is_file()]
        for j, path in enumerate(files, 1):
            zf.write(path, path.relative_to(work).as_posix())
            if j % 500 == 0 or j == len(files):
                print(f"  zip [{j}/{len(files)}]", flush=True)
    print(f"Wrote {pack} size={pack.stat().st_size/1024/1024:.2f}MB", flush=True)

    for dest in args.also_copy:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pack, dest)
        print(f"Copied -> {dest}")


if __name__ == "__main__":
    main()
