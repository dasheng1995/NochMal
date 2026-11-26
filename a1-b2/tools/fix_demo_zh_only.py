"""Restore Chinese glosses/examples into demo_a1_100.deword without re-fetching images."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zh_defs_a1_demo import DEF_ZH

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "http://127.0.0.1:10809"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ[k] = PROXY

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
PACK = ROOT / "packs" / "demo_a1_100.deword"
WORK = ROOT / "_demo_zh_fix_work"


def looks_chinese(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def zh_def(en: str) -> str:
    en = (en or "").strip()
    if en in DEF_ZH:
        return DEF_ZH[en]
    if looks_chinese(en):
        return en
    return DEF_ZH.get(en.lower(), en)


def make_translators():
    from deep_translator import GoogleTranslator, MyMemoryTranslator

    return [
        MyMemoryTranslator(source="en-GB", target="zh-CN"),
        GoogleTranslator(source="en", target="zh-CN"),
    ]


def translate_example(text: str, cache: dict[str, str], translators: list) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if text in cache:
        return cache[text]
    if looks_chinese(text):
        cache[text] = text
        return text
    out = ""
    for tr in translators:
        for _ in range(2):
            try:
                time.sleep(0.7)
                out = tr.translate(text) or ""
                if looks_chinese(out) and out != text:
                    cache[text] = out
                    return out
            except Exception as e:
                print("  translate fail", type(tr).__name__, type(e).__name__)
                time.sleep(1.2)
    cache[text] = out if looks_chinese(out) else ""
    return cache[text]


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    with zipfile.ZipFile(PACK, "r") as zf:
        zf.extractall(WORK)

    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    translators = make_translators()
    cache: dict[str, str] = {}

    unique_ex = sorted(
        {(w.get("example_en") or "").strip() for w in words if (w.get("example_en") or "").strip()}
    )
    print(f"Translating {len(unique_ex)} unique examples…")
    for i, ex in enumerate(unique_ex, 1):
        zh = translate_example(ex, cache, translators)
        print(f"  [{i}/{len(unique_ex)}] zh={bool(zh)} {ex[:60]}")

    for w in words:
        w["def_zh"] = zh_def(w.get("def_en") or "")
        w["example_zh"] = translate_example(w.get("example_en") or "", cache, translators)

    def_ok = sum(1 for w in words if looks_chinese(w.get("def_zh") or ""))
    ex_ok = sum(1 for w in words if looks_chinese(w.get("example_zh") or ""))
    print(f"Chinese defs={def_ok}/{len(words)} examples={ex_ok}/{len(words)}")
    if def_ok < len(words) * 0.9 or ex_ok < len(words) * 0.8:
        raise SystemExit("Chinese coverage too low; abort without overwriting pack")

    (WORK / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = 5
    manifest["notes"] = "Restored ZH defs+examples; images unchanged"
    manifest["content_hash"] = hashlib.sha256((WORK / "words.json").read_bytes()).hexdigest()[:16]
    (WORK / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # backup old pack then write
    bak = PACK.with_suffix(".deword.bak")
    if PACK.exists():
        shutil.copy2(PACK, bak)
    with zipfile.ZipFile(PACK, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(WORK).as_posix())
    print(f"Wrote {PACK} (backup {bak.name})")


if __name__ == "__main__":
    main()
