"""Unattended: finish B1 ZH+archive (images assumed ready/resume), then full B2."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
PY = sys.executable
TOOLS = ROOT / "tools"


def run(args: list[str]) -> int:
    print(f"\n>>> {' '.join(args)}", flush=True)
    p = subprocess.run(args, cwd=str(ROOT))
    print(f"<<< exit={p.returncode}", flush=True)
    if p.returncode != 0:
        raise SystemExit(p.returncode)
    return p.returncode


def image_ready_count(work: Path) -> tuple[int, int]:
    words = json.loads((work / "words.json").read_text(encoding="utf-8"))
    ready = sum(1 for w in words if (w.get("image") or {}).get("status") == "ready")
    return ready, len(words)


def ensure_work(pref: str) -> Path:
    work = ROOT / f"_{pref}_pack_work"
    pack = ROOT / "packs" / f"demo_{pref}.deword"
    if not (work / "words.json").exists():
        work.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(pack) as zf:
            zf.extractall(work)
    return work


def finish_zh_and_archive(level: str) -> None:
    pref = level.lower()
    pack = ROOT / "packs" / f"demo_{pref}.deword"
    work = ensure_work(pref)
    out = ROOT / "results" / f"{level}_final"
    out.mkdir(parents=True, exist_ok=True)
    (out / "work_snapshot").mkdir(exist_ok=True)

    run([PY, str(TOOLS / "repair_zh_from_dehelper.py"), "--pack", str(pack), "--work", str(work)])
    run([PY, str(TOOLS / "fill_level_examples_zh.py"), "--level", level])

    shutil.copy2(pack, out / pack.name)
    q = ROOT / "packs" / f"image_search_queries_{pref}.json"
    if q.exists():
        shutil.copy2(q, out / q.name)
    shutil.copy2(work / "words.json", out / "work_snapshot" / "words.json")
    shutil.copy2(work / "manifest.json", out / "work_snapshot" / "manifest.json")

    words = json.loads((work / "words.json").read_text(encoding="utf-8"))
    img = sum(1 for w in words if (w.get("image") or {}).get("status") == "ready")

    def has_zh(s: str) -> bool:
        return any("\u4e00" <= c <= "\u9fff" for c in (s or ""))

    dz = sum(1 for w in words if has_zh(w.get("def_zh") or ""))
    ez = sum(1 for w in words if has_zh(w.get("example_zh") or ""))
    (out / "README.md").write_text(
        f"# {level} Final Pack\n\n"
        f"- Pack: `{pack.name}`\n"
        f"- Words: {len(words)} | Images: {img} | def_zh: {dz} | example_zh: {ez}\n"
        f"- Pipeline: Pixabay (+ Wikimedia); def_zh Dehelper; example_zh GTX\n"
        f"- Created: unattended pipeline\n",
        encoding="utf-8",
    )
    print(f"Archived {level} -> {out} img={img}/{len(words)} zh={dz}/{ez}", flush=True)


def fill_until_complete(level: str, pref: str, max_rounds: int = 3) -> None:
    work = ensure_work(pref)
    for round_i in range(1, max_rounds + 1):
        ready, total = image_ready_count(work)
        print(f"{level} images before fill round {round_i}: {ready}/{total}", flush=True)
        if ready >= total and total > 0:
            return
        run([PY, str(TOOLS / "fill_level_images.py"), "--level", level])
        ready, total = image_ready_count(work)
        print(f"{level} images after fill round {round_i}: {ready}/{total}", flush=True)
        if ready >= total:
            return
        time.sleep(2)
    ready, total = image_ready_count(work)
    if ready < total:
        print(f"WARNING {level} still missing {total - ready} images — continuing", flush=True)


def main() -> None:
    print("UNATTENDED B1->B2 start", flush=True)

    # B1 finish
    ensure_work("b1")
    fill_until_complete("B1", "b1")
    finish_zh_and_archive("B1")

    # B2 full
    run([PY, str(TOOLS / "build_level_pack_skeleton.py"), "--level", "B2"])
    fill_until_complete("B2", "b2", max_rounds=5)
    finish_zh_and_archive("B2")
    print("ALL DONE B1+B2", flush=True)


if __name__ == "__main__":
    main()
