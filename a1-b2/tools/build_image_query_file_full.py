"""Build file A (image_search_queries JSON) for ALL words in the Frequency apkg.

Same schema as packs/image_search_queries_demo100.json.
Source: English-Deutsch (Sorted by Frequency)-20261124232300.apkg
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_image_query_file_a import VISUAL_OVERRIDE, build_query
from build_image_query_file_a100 import EXTRA_OVERRIDE
from zh_defs_a1_demo import DEF_ZH

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
DB = ROOT / "_apkg_extract" / "collection_decomp.anki2"
OUT = ROOT / "packs" / "image_search_queries_all.json"
MAIN_NT = 1776081424953
SEP = "\x1f"


def normalize_level(raw: str) -> str:
    s = (raw or "").strip().upper()
    if s.startswith("A1"):
        return "A1"
    if s.startswith("A2"):
        return "A2"
    if s.startswith("B1"):
        return "B1"
    if s.startswith("B2"):
        return "B2"
    return s or "UNK"


def level_prefix(level: str) -> str:
    return {
        "A1": "a1",
        "A2": "a2",
        "B1": "b1",
        "B2": "b2",
    }.get(level, level.lower().replace("+", "").replace(" ", "") or "x")


def zh_def(en: str) -> str:
    en = (en or "").strip()
    if not en:
        return ""
    if en in DEF_ZH:
        return DEF_ZH[en]
    if en.lower() in DEF_ZH:
        return DEF_ZH[en.lower()]
    # mild fallback: first sense key
    first = re.split(r"[,;/]", en)[0].strip()
    if first in DEF_ZH:
        return DEF_ZH[first]
    return ""


def field_map(conn: sqlite3.Connection) -> dict[int, str]:
    return {
        ord_: name
        for ntid, ord_, name in conn.execute(
            "SELECT ntid, ord, name FROM fields WHERE ntid=? ORDER BY ord",
            (MAIN_NT,),
        )
    }


def load_words() -> list[dict]:
    if not DB.exists():
        raise SystemExit(f"Missing DB: {DB}. Extract the apkg first.")

    conn = sqlite3.connect(str(DB))
    fmap = field_map(conn)
    name_to_ord = {v: k for k, v in fmap.items()}
    words: list[dict] = []

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

        level = normalize_level(get("Level"))
        rank_raw = get("Rank")
        try:
            rank = int(float(rank_raw)) if rank_raw else len(words) + 1
        except ValueError:
            rank = len(words) + 1

        lemma = get("Word")
        if not lemma:
            continue

        def_en = get("Definition 1")
        example_en = get("English 1")
        example_de = get("German 1")
        pos = get("Part-of-Speech 1")
        wid = f"{level_prefix(level)}_{rank}_{nid}"

        words.append(
            {
                "id": wid,
                "rank": rank,
                "level": level,
                "lemma": lemma,
                "pos": pos,
                "def_en": def_en,
                "def_zh": zh_def(def_en),
                "example_de": example_de,
                "example_en": example_en,
                # Example ZH filled later in a dedicated pass; keep empty for now.
                "example_zh": "",
                "frequency": get("Frequency"),
                "tags": tags.split(),
            }
        )

    conn.close()
    # Stable order: by rank then id
    words.sort(key=lambda w: (w["rank"], w["id"]))
    return words


def main():
    VISUAL_OVERRIDE.update(EXTRA_OVERRIDE)

    words = load_words()
    items = []
    for w in words:
        item = build_query(w)
        item["level"] = w["level"]
        item["rank"] = w["rank"]
        if not item.get("search_en"):
            # last-resort fallback so image agent never gets empty query
            item["search_en"] = (w.get("def_en") or w.get("lemma") or "object").strip()
            item["search_note"] = (item.get("search_note") or "") + "; empty-query fallback"
        items.append(item)

    by_level = Counter(i["level"] for i in items)
    by_branch = Counter(i["branch"] for i in items)
    empty_zh = sum(1 for i in items if not (i.get("def_zh") or "").strip())
    empty_q = sum(1 for i in items if not (i.get("search_en") or "").strip())

    file_a = {
        "format": "image_search_queries",
        "version": 1,
        "pack_id": "all_frequency",
        "source_apkg": "English-Deutsch (Sorted by Frequency)-20261124232300.apkg",
        "word_count": len(items),
        "level_counts": dict(sorted(by_level.items())),
        "branch_counts": dict(sorted(by_branch.items())),
        "rules": {
            "branch_A": "noun/verb -> English gloss / progressive scene",
            "branch_B": "adj/adv/other -> 2-3 visual nouns from example",
            "sources": "Pixabay/Pexels (API key) -> Wikimedia fallback",
            "pipeline": "same as demo_a1_100 successful Pixabay fill",
            "next_agent": "Search with search_en; download crop webp -> images/{word_id}.webp",
            "note_zh": "def_zh filled when in zh_defs map; example_zh left empty for a later ZH pass",
        },
        "items": items,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")
    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"Wrote {OUT}")
    print(f"words={len(items)} size={size_mb:.2f}MB")
    print(f"levels={dict(by_level)}")
    print(f"branches={dict(by_branch)}")
    print(f"empty def_zh={empty_zh} empty search_en={empty_q}")
    for i in items[:5]:
        print(f"  [{i['level']}/{i['branch']}] {i['lemma_core'][:20]:20} -> {i['search_en']}")
    print("  ...")
    for i in items[-3:]:
        print(f"  [{i['level']}/{i['branch']}] {i['lemma_core'][:20]:20} -> {i['search_en']}")


if __name__ == "__main__":
    main()
