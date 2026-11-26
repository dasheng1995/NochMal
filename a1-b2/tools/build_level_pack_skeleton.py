"""Build deword skeleton + file A for one CEFR level (A1/A2/B1/B2)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_demo_pack import MAIN_NT, SEP, copy_audio, field_map, load_media_map, sound_name
from zh_defs_a1_demo import DEF_ZH

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
DB = ROOT / "_apkg_extract" / "collection_decomp.anki2"
ALL_QUERIES = ROOT / "packs" / "image_search_queries_all.json"


def normalize_level(raw: str, want: str) -> bool:
    s = (raw or "").strip().upper()
    want = want.upper()
    if want == "B2":
        return s.startswith("B2")
    return s == want or s.startswith(want)


def level_prefix(level: str) -> str:
    return {"A1": "a1", "A2": "a2", "B1": "b1", "B2": "b2"}[level.upper()]


def zh_def(en: str) -> str:
    en = (en or "").strip()
    if not en:
        return ""
    if en in DEF_ZH:
        return DEF_ZH[en]
    first = re.split(r"[,;/]", en)[0].strip()
    return DEF_ZH.get(first, "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", required=True, choices=["A1", "A2", "B1", "B2"])
    args = ap.parse_args()
    level = args.level.upper()
    pref = level_prefix(level)

    out_queries = ROOT / "packs" / f"image_search_queries_{pref}.json"
    work = ROOT / f"_{pref}_pack_work"
    out_pack = ROOT / "packs" / f"demo_{pref}.deword"

    all_a = json.loads(ALL_QUERIES.read_text(encoding="utf-8"))
    items = [it for it in all_a["items"] if normalize_level(it.get("level") or "", level)]
    if not items:
        raise SystemExit(f"no items for {level}")

    file_a = {
        "format": "image_search_queries",
        "version": 1,
        "pack_id": f"demo_{pref}",
        "word_count": len(items),
        "level_counts": {level: len(items)},
        "rules": {
            **(all_a.get("rules") or {}),
            "next_agent": "fill_level_images.py",
            "pipeline": "Pixabay + Wikimedia; ZH via Dehelper",
        },
        "items": items,
    }
    for it in file_a["items"]:
        it["image_status"] = "pending"
        it.pop("image_source", None)
        it["level"] = level
    out_queries.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_queries} items={len(items)}")

    by_id_query = {it["word_id"]: it for it in items}
    media_map = load_media_map()
    conn = sqlite3.connect(str(DB))
    fmap = field_map(conn)
    name_to_ord = {v: k for k, v in fmap.items()}

    if work.exists():
        shutil.rmtree(work)
    (work / "audio").mkdir(parents=True)
    (work / "images").mkdir(parents=True)

    words = []
    audio_ok = 0
    for nid, tags, flds in conn.execute(
        "SELECT id, tags, flds FROM notes WHERE mid=? ORDER BY id",
        (MAIN_NT,),
    ):
        parts = flds.split(SEP)

        def get(name: str) -> str:
            i = name_to_ord.get(name)
            if i is None or i >= len(parts):
                return ""
            return parts[i].strip()

        if not normalize_level(get("Level"), level):
            continue

        rank_raw = get("Rank")
        try:
            rank = int(float(rank_raw)) if rank_raw else len(words) + 1
        except ValueError:
            rank = len(words) + 1
        wid = f"{pref}_{rank}_{nid}"
        qitem = by_id_query.get(wid)
        if not qitem:
            print("  skip missing query", wid, get("Word"))
            continue

        lemma = get("Word")
        def_en = get("Definition 1")
        example_de = get("German 1")
        example_en = get("English 1")
        pos = get("Part-of-Speech 1")
        ipa = get("IPA")

        audio_word_rel = None
        word_audio = sound_name(get("WordAudio"))
        if word_audio:
            dest = work / "audio" / f"{wid}_word.mp3"
            if copy_audio(media_map, word_audio, dest):
                audio_word_rel = f"audio/{wid}_word.mp3"
                audio_ok += 1

        audio_sent_rel = None
        sent_audio = sound_name(get("SentenceAudio1"))
        if sent_audio:
            dest = work / "audio" / f"{wid}_s1.mp3"
            if copy_audio(media_map, sent_audio, dest):
                audio_sent_rel = f"audio/{wid}_s1.mp3"
                audio_ok += 1

        words.append(
            {
                "id": wid,
                "rank": rank,
                "lemma": lemma,
                "ipa": ipa,
                "level": level,
                "pos": pos,
                "def_en": def_en,
                "def_zh": zh_def(def_en) or qitem.get("def_zh") or "",
                "example_de": example_de,
                "example_en": example_en,
                "example_zh": qitem.get("example_zh") or "",
                "audio_word": audio_word_rel,
                "audio_sentence": audio_sent_rel,
                "image": {
                    "path": "",
                    "source": "",
                    "query_or_prompt": qitem["search_en"],
                    "status": "pending",
                },
                "tags": tags.split() or [level],
            }
        )

    conn.close()
    words.sort(key=lambda w: (w["rank"], w["id"]))
    print(f"words={len(words)} audio_files~={audio_ok}")

    (work / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "format": "deword",
        "version": 1,
        "level": level,
        "pack_id": f"demo_{pref}",
        "title": f"Demo {level}",
        "word_count": len(words),
        "content_hash": hashlib.sha256((work / "words.json").read_bytes()).hexdigest()[:16],
        "notes": f"{level} pack skeleton; images pending",
        "image_status": "pending",
        "query_file": out_queries.name,
    }
    (work / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if out_pack.exists():
        out_pack.unlink()
    with zipfile.ZipFile(out_pack, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in work.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(work).as_posix())
    print(f"Wrote skeleton {out_pack} size={out_pack.stat().st_size/1024/1024:.2f}MB")


if __name__ == "__main__":
    main()
