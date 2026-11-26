"""Build A2 deword skeleton (words.json + audio + empty images) and file A slice."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_demo_pack import (
    MAIN_NT,
    SEP,
    copy_audio,
    field_map,
    load_media_map,
    sound_name,
)
from zh_defs_a1_demo import DEF_ZH

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
DB = ROOT / "_apkg_extract" / "collection_decomp.anki2"
ALL_QUERIES = ROOT / "packs" / "image_search_queries_all.json"
OUT_QUERIES = ROOT / "packs" / "image_search_queries_a2.json"
WORK = ROOT / "_a2_pack_work"
OUT_PACK = ROOT / "packs" / "demo_a2.deword"


def normalize_level(raw: str) -> str:
    s = (raw or "").strip().upper()
    if s.startswith("A2"):
        return "A2"
    return s


def zh_def(en: str) -> str:
    en = (en or "").strip()
    if not en:
        return ""
    if en in DEF_ZH:
        return DEF_ZH[en]
    first = re.split(r"[,;/]", en)[0].strip()
    return DEF_ZH.get(first, "")


def main():
    if not ALL_QUERIES.exists():
        raise SystemExit(f"missing {ALL_QUERIES}")
    all_a = json.loads(ALL_QUERIES.read_text(encoding="utf-8"))
    items = [it for it in all_a["items"] if it.get("level") == "A2"]
    if not items:
        raise SystemExit("no A2 items in all queries file")

    file_a = {
        "format": "image_search_queries",
        "version": 1,
        "pack_id": "demo_a2",
        "word_count": len(items),
        "level_counts": {"A2": len(items)},
        "rules": {
            **(all_a.get("rules") or {}),
            "next_agent": "fill_a2_images.py",
            "pipeline": "same as demo_a1_100 Pixabay fill",
        },
        "items": items,
    }
    for it in file_a["items"]:
        it["image_status"] = "pending"
        it.pop("image_source", None)
    OUT_QUERIES.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_QUERIES} items={len(items)}")

    by_id_query = {it["word_id"]: it for it in items}
    media_map = load_media_map()
    conn = sqlite3.connect(str(DB))
    fmap = field_map(conn)
    name_to_ord = {v: k for k, v in fmap.items()}

    if WORK.exists():
        shutil.rmtree(WORK)
    (WORK / "audio").mkdir(parents=True)
    (WORK / "images").mkdir(parents=True)

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

        if normalize_level(get("Level")) != "A2":
            continue

        rank_raw = get("Rank")
        try:
            rank = int(float(rank_raw)) if rank_raw else len(words) + 1
        except ValueError:
            rank = len(words) + 1
        wid = f"a2_{rank}_{nid}"
        qitem = by_id_query.get(wid)
        if not qitem:
            # fallback match by rank+nid pattern already exact; skip if missing
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
            dest = WORK / "audio" / f"{wid}_word.mp3"
            if copy_audio(media_map, word_audio, dest):
                audio_word_rel = f"audio/{wid}_word.mp3"
                audio_ok += 1

        audio_sent_rel = None
        sent_audio = sound_name(get("SentenceAudio1"))
        if sent_audio:
            dest = WORK / "audio" / f"{wid}_s1.mp3"
            if copy_audio(media_map, sent_audio, dest):
                audio_sent_rel = f"audio/{wid}_s1.mp3"
                audio_ok += 1

        words.append(
            {
                "id": wid,
                "rank": rank,
                "lemma": lemma,
                "ipa": ipa,
                "level": "A2",
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
                "tags": tags.split() or ["A2"],
            }
        )

    conn.close()
    words.sort(key=lambda w: (w["rank"], w["id"]))
    print(f"words={len(words)} audio_files~={audio_ok}")

    (WORK / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "format": "deword",
        "version": 1,
        "level": "A2",
        "pack_id": "demo_a2",
        "title": "Demo A2",
        "word_count": len(words),
        "content_hash": hashlib.sha256((WORK / "words.json").read_bytes()).hexdigest()[:16],
        "notes": "A2 pack skeleton; images pending Pixabay fill",
        "image_status": "pending",
        "query_file": "image_search_queries_a2.json",
    }
    (WORK / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if OUT_PACK.exists():
        OUT_PACK.unlink()
    with zipfile.ZipFile(OUT_PACK, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(WORK).as_posix())
    print(f"Wrote skeleton {OUT_PACK} size={OUT_PACK.stat().st_size/1024/1024:.2f}MB")


if __name__ == "__main__":
    main()
