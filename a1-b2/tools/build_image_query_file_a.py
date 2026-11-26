"""
Step 1: Build local file A — English image-search queries for each word.
Step 2: Build a 20-word demo pack with image slots cleared.

Branch A (noun / verb): search cleaned English gloss / lemma concept.
Branch B (adj / adv / other): extract 2–3 visual English nouns from the example.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
SRC_PACK = ROOT / "packs" / "demo_a1_100.deword"
OUT_QUERIES = ROOT / "packs" / "image_search_queries_demo20.json"  # file A
OUT_PACK = ROOT / "packs" / "demo_a1_20.deword"
WORK = ROOT / "_demo20_work"

BRANCH_A_POS = {"verb", "n", "noun", "der", "die", "das"}
# everything else -> B (art, prep, conj, pron, part, adv, adj, ...)

# Hand-tuned visual queries for common function words / hard cases (demo quality).
VISUAL_OVERRIDE = {
    "der": ("B", "man woman child cooking kitchen", "article; use example scene"),
    "und": ("B", "family eating dinner together table", "conj; example scene"),
    "in": ("B", "person walking into basement doorway", "prep; example scene"),
    "sein, ist, war, ist gewesen": ("A", "teacher police officer people", "verb to be"),
    "ein": ("B", "hotel building exterior", "article; example scene"),
    "haben, hat, hatte, hat gehabt": ("A", "hand holding book", "verb to have + example object"),
    "sie": ("B", "woman visiting relative home", "pronoun; example scene"),
    "werden, wird, wurde, ist geworden": ("A", "boy growing into man", "verb become"),
    "von": ("B", "brother sister family portrait", "prep; example scene"),
    "ich": ("B", "person working at home desk", "pronoun; example scene"),
    "nicht": ("B", "no smoking sign restaurant", "particle; example scene"),
    "es": ("B", "tired child going to bed", "pronoun; example scene"),
    "mit": ("B", "boys playing soccer garden", "prep; example scene"),
    "sich": ("B", "child looking in mirror", "pronoun; example scene"),
    "er": ("B", "smart student school grades", "pronoun; example scene"),
    "auf": ("B", "glass of water on table", "prep; example scene"),
    "für": ("B", "making coffee for someone cup", "prep; example scene"),
    "auch": ("B", "birthday celebration friends", "adv; example scene"),
    "an": ("B", "picture frame hanging on wall", "prep; example scene"),
    "dass": ("B", "late train at station clock", "conj; example scene"),
    "können, kann, konnte, hat können": ("A", "children riding bicycle", "verb can; example scene"),
    "zu": ("B", "person listening trying to understand", "particle; example scene"),
    "sagen, sagt, sagte, hat gesagt": ("A", "colleagues talking office", "verb say; example scene"),
}


def clean_lemma(lemma: str) -> str:
    s = lemma.split(",")[0].strip()
    s = re.sub(r"^(der|die|das)\s+", "", s, flags=re.I)
    return s


def clean_gloss_en(def_en: str) -> str:
    s = (def_en or "").strip()
    s = re.sub(r"^to\s+", "", s, flags=re.I)
    s = re.split(r"[,;/]", s)[0].strip()
    s = re.sub(r"\s*\(.*?\)\s*", " ", s).strip()
    return s


def is_branch_a(pos: str) -> bool:
    p = (pos or "").strip().lower()
    return p in BRANCH_A_POS or p.startswith("v")


def extract_visual_from_example(example_en: str, def_zh: str, def_en: str) -> str:
    """Heuristic 2–3 visual nouns from English example (demo; LLM can replace later)."""
    text = (example_en or "").lower()
    # light stopword strip, keep concrete nouns
    stop = {
        "a", "an", "the", "and", "or", "to", "of", "in", "on", "at", "for", "with",
        "is", "are", "was", "were", "be", "been", "am", "i", "you", "he", "she",
        "it", "we", "they", "my", "your", "his", "her", "our", "their", "this",
        "that", "have", "has", "had", "do", "does", "did", "will", "would", "can",
        "could", "should", "must", "may", "me", "him", "them", "us", "not", "no",
        "yes", "so", "as", "if", "when", "than", "then", "very", "just", "also",
        "only", "into", "from", "by", "about", "over", "after", "before", "again",
    }
    tokens = re.findall(r"[a-zA-Z']+", text)
    keep = [t for t in tokens if t.lower() not in stop and len(t) > 2]
    # prefer nouns-ish longer words
    picked = []
    for t in keep:
        if t.lower() not in {p.lower() for p in picked}:
            picked.append(t)
        if len(picked) >= 3:
            break
    if not picked:
        g = clean_gloss_en(def_en) or (def_zh or "object")
        return g
    return " ".join(picked[:3])


def build_query(word: dict) -> dict:
    lemma = word["lemma"]
    pos = word.get("pos") or ""
    def_en = word.get("def_en") or ""
    def_zh = word.get("def_zh") or ""
    example_de = word.get("example_de") or ""
    example_en = word.get("example_en") or ""
    example_zh = word.get("example_zh") or ""

    if lemma in VISUAL_OVERRIDE:
        branch, query, note = VISUAL_OVERRIDE[lemma]
    elif is_branch_a(pos):
        branch = "A"
        base = clean_gloss_en(def_en)
        # verb -> prefer progressive / person scene when short abstract
        if (pos or "").lower() == "verb":
            if base in {"be", "have", "become", "can", "must", "want", "know", "say"}:
                query = extract_visual_from_example(example_en, def_zh, def_en)
                note = "verb abstract -> example visual"
            else:
                # e.g. come -> person coming / go -> person walking
                query = f"person {base}ing" if not base.endswith("e") else f"person {base[:-1]}ing"
                if len(base) <= 3:
                    query = extract_visual_from_example(example_en, def_zh, def_en)
                note = "verb gloss / progressive"
        else:
            # noun: if Chinese sense needs disambiguation, append hint words already in gloss
            query = base
            note = "noun/core gloss"
    else:
        branch = "B"
        query = extract_visual_from_example(example_en, def_zh, def_en)
        note = "non n/v -> example visual nouns"

    query = re.sub(r"\s+", " ", query).strip()
    return {
        "word_id": word["id"],
        "lemma": lemma,
        "lemma_core": clean_lemma(lemma),
        "pos": pos,
        "def_en": def_en,
        "def_zh": def_zh,
        "example_de": example_de,
        "example_en": example_en,
        "example_zh": example_zh,
        "branch": branch,
        "search_en": query,
        "search_note": note,
        "image_status": "pending",
        "preferred_sources": ["pixabay", "pexels", "openverse", "wikimedia"],
        "avoid_sources": ["unsplash_bulk_download"],
    }


def select_twenty(words: list[dict]) -> list[dict]:
    """Prefer a POS mix; fall back to rank order."""
    want = [
        "verb", "verb", "verb", "verb",
        "prep", "prep", "prep", "prep",
        "pron", "pron", "pron",
        "conj", "conj",
        "art", "art",
        "adv", "part", "part",
        "pron", "verb",
    ]
    picked = []
    used = set()
    by_pos: dict[str, list] = {}
    for w in words:
        by_pos.setdefault((w.get("pos") or "").lower(), []).append(w)
    for p in want:
        bucket = by_pos.get(p) or []
        for w in bucket:
            if w["id"] not in used:
                picked.append(w)
                used.add(w["id"])
                break
        if len(picked) >= 20:
            break
    for w in words:
        if len(picked) >= 20:
            break
        if w["id"] not in used:
            picked.append(w)
            used.add(w["id"])
    return picked[:20]


def main():
    with zipfile.ZipFile(SRC_PACK, "r") as zf:
        all_words = json.loads(zf.read("words.json").decode("utf-8"))
        # keep media map by extracting fully then trimming
        if WORK.exists():
            shutil.rmtree(WORK)
        WORK.mkdir(parents=True)
        zf.extractall(WORK)

    selected = select_twenty(all_words)
    queries = [build_query(w) for w in selected]

    file_a = {
        "format": "image_search_queries",
        "version": 1,
        "pack_id": "demo_a1_20",
        "word_count": len(queries),
        "rules": {
            "branch_A": "noun/verb -> English gloss / progressive scene",
            "branch_B": "adj/adv/other -> 2-3 visual nouns from example",
            "next_agent": "Search Pixabay/Pexels/Openverse/Wikimedia with search_en; download crop webp; fill pack images/",
        },
        "items": queries,
    }
    OUT_QUERIES.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote file A: {OUT_QUERIES}")

    # Step 2: build 20-word pack with images cleared
    id_set = {q["word_id"] for q in queries}
    slim = []
    for w in all_words:
        if w["id"] not in id_set:
            continue
        w = dict(w)
        # clear image payload; keep slot schema
        w["image"] = {
            "path": "",
            "source": "",
            "query_or_prompt": next(q["search_en"] for q in queries if q["word_id"] == w["id"]),
            "status": "pending",
        }
        # drop old audio? keep audio for demo UX
        slim.append(w)

    # remove old images from work copy; keep only selected audio
    img_dir = WORK / "images"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    img_dir.mkdir(parents=True, exist_ok=True)

    # prune audio not in selected
    keep_audio = set()
    for w in slim:
        for k in ("audio_word", "audio_sentence"):
            p = w.get(k)
            if p:
                keep_audio.add(p.replace("\\", "/"))
    audio_dir = WORK / "audio"
    if audio_dir.exists():
        for f in audio_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(WORK).as_posix()
                if rel not in keep_audio:
                    f.unlink()

    (WORK / "words.json").write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "format": "deword",
        "version": 1,
        "level": "A1",
        "pack_id": "demo_a1_20",
        "title": "Demo A1 20 (images pending)",
        "word_count": len(slim),
        "content_hash": hashlib.sha256((WORK / "words.json").read_bytes()).hexdigest()[:16],
        "notes": "Images cleared. Use image_search_queries_demo20.json as file A for image agent.",
        "image_status": "pending",
        "query_file": "image_search_queries_demo20.json",
    }
    (WORK / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if OUT_PACK.exists():
        OUT_PACK.unlink()
    with zipfile.ZipFile(OUT_PACK, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file():
                # skip leftover unused files
                rel = path.relative_to(WORK).as_posix()
                if rel.startswith("images/") and path.stat().st_size == 0:
                    continue
                zf.write(path, rel)
    print(f"Wrote pack: {OUT_PACK} words={len(slim)}")
    for q in queries:
        print(f"  [{q['branch']}] {q['lemma'][:28]:28} -> {q['search_en']}")


if __name__ == "__main__":
    main()
