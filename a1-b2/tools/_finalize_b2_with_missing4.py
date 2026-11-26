"""Re-apply missing4 images into B2 work+pack+results archive."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
WORK = ROOT / "_b2_pack_work"
PACK = ROOT / "packs" / "demo_b2.deword"
OUT = ROOT / "results" / "B2_final"
PATCH = WORK / "_missing4_image_patch.json"


def has_zh(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in (s or ""))


def main() -> None:
    # reapply patch
    patch = json.loads(PATCH.read_text(encoding="utf-8")) if PATCH.exists() else {}
    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
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
        n += 1
    print(f"patched {n}")
    ready = sum(1 for w in words if (w.get("image") or {}).get("status") == "ready")
    dz = sum(1 for w in words if has_zh(w.get("def_zh") or ""))
    ez = sum(1 for w in words if has_zh(w.get("example_zh") or ""))
    (WORK / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    manifest["image_status"] = "filled" if ready == len(words) else f"partial:{ready}/{len(words)}"
    manifest["zh_status"] = f"defs={dz}/{len(words)} examples={ez}/{len(words)}"
    manifest["content_hash"] = hashlib.sha256((WORK / "words.json").read_bytes()).hexdigest()[:16]
    (WORK / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if PACK.exists():
        PACK.unlink()
    files = [p for p in WORK.rglob("*") if p.is_file() and not p.name.startswith("_missing4")]
    with zipfile.ZipFile(PACK, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            zf.write(p, p.relative_to(WORK).as_posix())
    print(f"pack {PACK.stat().st_size/1024/1024:.2f}MB img={ready}/{len(words)} zh={dz}/{ez}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "work_snapshot").mkdir(exist_ok=True)
    shutil.copy2(PACK, OUT / PACK.name)
    q = ROOT / "packs" / "image_search_queries_b2.json"
    if q.exists():
        shutil.copy2(q, OUT / q.name)
    shutil.copy2(WORK / "words.json", OUT / "work_snapshot" / "words.json")
    shutil.copy2(WORK / "manifest.json", OUT / "work_snapshot" / "manifest.json")
    (OUT / "README.md").write_text(
        f"# B2 Final Pack\n\n"
        f"- Pack: `demo_b2.deword`\n"
        f"- Words: {len(words)} | Images: {ready} | def_zh: {dz} | example_zh: {ez}\n"
        f"- Pipeline: Pixabay (+ Wikimedia); def_zh Dehelper; example_zh GTX\n"
        f"- Note: 4 late fills (zerreißen/Landsmann/Spielraum/Neigung) after 429\n",
        encoding="utf-8",
    )
    print(f"archived -> {OUT}")


if __name__ == "__main__":
    main()
