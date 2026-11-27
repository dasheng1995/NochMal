"""Repair def_zh in a .deword pack using local Dehelper dictionary.

Writes:
  - def_zh: up to 2 Chinese senses (quiz options)
  - def_zh_full: all Chinese senses from Dehelper (detail page)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

import dehelper_lookup as dh

POS_PREFIX = re.compile(
    r"^(?:[mnfMNF]\.|Vt\.|Vi\.|vt\.|vi\.|Adj\.|Adv\.|adj\.|adv\.|"
    r"Präp\.|Konj\.|Pron\.|Art\.|Num\.|pl\.)\s*"
)


def looks_chinese(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def strip_pos_prefix(g: str) -> str:
    return POS_PREFIX.sub("", (g or "").strip()).strip()


def sense_list(gloss: str) -> list[str]:
    """Split a Dehelper gloss into Chinese sense chunks (by ；/; )."""
    s = strip_pos_prefix(gloss)
    if not s:
        return []
    parts = re.split(r"[;；]", s)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        p = p.strip().strip("、,， ")
        p = re.sub(r"\s+", "", p)
        if not p or not looks_chinese(p):
            continue
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def senses_from_hits(hits: list[dict]) -> list[str]:
    if not hits:
        return []
    senses = sense_list(hits[0].get("def_zh") or "")
    kind0 = hits[0].get("kind") or "plain"
    for h in hits[1:6]:
        kind = h.get("kind") or "plain"
        if kind0 != "plain" and kind not in (kind0, "plain"):
            continue
        for s in sense_list(h.get("def_zh") or ""):
            if s not in senses:
                senses.append(s)
    return senses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True, help="output .deword path")
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=None, help="extract from this pack if work empty")
    ap.add_argument("--also-copy", type=Path, action="append", default=[])
    args = ap.parse_args()

    pack: Path = args.pack
    work: Path = args.work
    source: Path = args.source or pack
    work.mkdir(parents=True, exist_ok=True)

    if not (work / "words.json").exists():
        if not source.exists():
            raise SystemExit(f"missing source pack: {source}")
        print(f"extracting {source} -> {work}", flush=True)
        with zipfile.ZipFile(source, "r") as zf:
            zf.extractall(work)

    words = json.loads((work / "words.json").read_text(encoding="utf-8"))
    print(f"loading dict {dh.DIC} …", flush=True)
    data = dh.DIC.read_bytes()
    print(f"dict {len(data)/1024/1024:.1f}MB words={len(words)}", flush=True)

    changed = 0
    found = 0
    missing: list[str] = []
    for i, w in enumerate(words, 1):
        lemma = w.get("lemma") or ""
        pos = w.get("pos") or ""
        hits = dh.lookup(lemma, data=data, pos=pos)
        if not hits:
            missing.append(lemma)
            # keep existing; ensure full fallback
            if not (w.get("def_zh_full") or "").strip() and (w.get("def_zh") or "").strip():
                w["def_zh_full"] = w["def_zh"]
        else:
            found += 1
            senses = senses_from_hits(hits)
            if not senses:
                short = strip_pos_prefix(hits[0].get("def_zh_short") or hits[0].get("def_zh") or "")
                full = strip_pos_prefix(hits[0].get("def_zh") or short)
                senses = [short] if short else []
                if full and full not in senses:
                    senses = sense_list(full) or ([full] if looks_chinese(full) else senses)
            new_full = "；".join(senses)
            new_short = "；".join(senses[:2])
            prev_zh = w.get("def_zh") or ""
            prev_full = w.get("def_zh_full") or ""
            if prev_zh != new_short or prev_full != new_full:
                changed += 1
            w["def_zh"] = new_short
            w["def_zh_full"] = new_full
            w["def_zh_source"] = "dehelper"
        if i % 100 == 0 or i == len(words):
            print(f"  lookup [{i}/{len(words)}] hit={found} changed={changed}", flush=True)

    print(
        f"words={len(words)} dehelper_hit={found} changed={changed} missing={len(missing)}",
        flush=True,
    )
    if missing[:15]:
        print("missing sample:", missing[:15], flush=True)

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
    manifest["zh_def_note"] = "def_zh<=2 senses; def_zh_full=all Dehelper Chinese senses"
    manifest["content_hash"] = hashlib.sha256((work / "words.json").read_bytes()).hexdigest()[:16]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("repacking deword (may take a few minutes) …", flush=True)
    pack.parent.mkdir(parents=True, exist_ok=True)
    tmp = pack.with_suffix(".deword.tmp")
    if tmp.exists():
        tmp.unlink()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        files = [p for p in work.rglob("*") if p.is_file()]
        for j, path in enumerate(files, 1):
            zf.write(path, path.relative_to(work).as_posix())
            if j % 500 == 0 or j == len(files):
                print(f"  zip [{j}/{len(files)}]", flush=True)
    if pack.exists():
        pack.unlink()
    tmp.rename(pack)
    print(f"Wrote {pack} size={pack.stat().st_size/1024/1024:.2f}MB", flush=True)

    for dest in args.also_copy:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pack, dest)
        print(f"Copied -> {dest}")


if __name__ == "__main__":
    main()
