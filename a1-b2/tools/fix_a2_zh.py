"""Fill Chinese defs/examples for A2 pack via Google GTX (proxy) + MyMemory fallback (no proxy)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zh_defs_a1_demo import DEF_ZH

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "http://127.0.0.1:10809"
ROOT = Path(r"e:\local_project\deutsch\a1-b2")
PACK = ROOT / "packs" / "demo_a2.deword"
WORK = ROOT / "_a2_pack_work"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def looks_chinese(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def zh_def_map(en: str) -> str:
    en = (en or "").strip()
    if not en:
        return ""
    if looks_chinese(en):
        return en
    if en in DEF_ZH:
        return DEF_ZH[en]
    first = re.split(r"[,;/]", en)[0].strip()
    return DEF_ZH.get(first, "")


def translate_gtx(text: str, op, timeout: int = 15) -> str:
    q = urllib.parse.urlencode(
        {"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text}
    )
    url = "https://translate.googleapis.com/translate_a/single?" + q
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with op.open(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    parts = []
    for row in data[0] or []:
        if row and row[0]:
            parts.append(row[0])
    out = "".join(parts).strip()
    return out if looks_chinese(out) else ""


def translate_mymemory_noproxy(text: str, timeout: int = 15) -> str:
    q = urllib.parse.urlencode({"q": text, "langpair": "en|zh-CN"})
    url = "https://api.mymemory.translated.net/get?" + q
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with op.open(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    out = (((data or {}).get("responseData") or {}).get("translatedText") or "").strip()
    return out if looks_chinese(out) else ""


def translate_one(text: str, gtx_op) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if looks_chinese(text):
        return text
    for attempt in range(3):
        try:
            out = translate_gtx(text, gtx_op)
            if out:
                return out
        except Exception as e:
            if attempt == 2:
                print(f"  gtx err: {type(e).__name__}", flush=True)
            time.sleep(1.2 + attempt)
        try:
            out = translate_mymemory_noproxy(text)
            if out:
                return out
        except Exception:
            time.sleep(0.8)
    return ""


def save_pack(words: list[dict], def_ok: int, ex_ok: int) -> None:
    (WORK / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = max(int(manifest.get("version") or 1), 3)
    manifest["notes"] = "A2 pack: Pixabay images + ZH defs/examples"
    manifest["zh_status"] = f"defs={def_ok}/{len(words)} examples={ex_ok}/{len(words)}"
    manifest["image_status"] = "filled"
    manifest["content_hash"] = hashlib.sha256((WORK / "words.json").read_bytes()).hexdigest()[:16]
    (WORK / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if PACK.exists():
        PACK.unlink()
    with zipfile.ZipFile(PACK, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(WORK).as_posix())


def main():
    print("loading…", flush=True)
    if not (WORK / "words.json").exists():
        with zipfile.ZipFile(PACK, "r") as zf:
            zf.extractall(WORK)

    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    gtx_op = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )

    cache: dict[str, str] = {}

    # defs
    for w in words:
        mapped = zh_def_map(w.get("def_en") or "")
        if mapped:
            w["def_zh"] = mapped

    need_defs = sorted(
        {
            (w.get("def_en") or "").strip()
            for w in words
            if (w.get("def_en") or "").strip() and not looks_chinese(w.get("def_zh") or "")
        }
    )
    print(f"defs to translate: {len(need_defs)}", flush=True)
    for i, text in enumerate(need_defs, 1):
        zh = translate_one(text, gtx_op)
        cache[text] = zh
        if i % 25 == 0 or i == len(need_defs):
            ok = sum(1 for v in cache.values() if v)
            print(f"  def [{i}/{len(need_defs)}] ok={ok}", flush=True)
        time.sleep(0.35)

    for w in words:
        if not looks_chinese(w.get("def_zh") or ""):
            w["def_zh"] = cache.get((w.get("def_en") or "").strip(), "") or w.get("def_zh") or ""

    def_ok = sum(1 for w in words if looks_chinese(w.get("def_zh") or ""))
    save_pack(words, def_ok, 0)
    print(f"checkpoint defs={def_ok}/{len(words)}", flush=True)

    # examples
    need_ex = sorted(
        {
            (w.get("example_en") or "").strip()
            for w in words
            if (w.get("example_en") or "").strip() and not looks_chinese(w.get("example_zh") or "")
        }
    )
    print(f"examples to translate: {len(need_ex)}", flush=True)
    for i, text in enumerate(need_ex, 1):
        zh = translate_one(text, gtx_op)
        cache[text] = zh
        if i % 25 == 0 or i == len(need_ex):
            ok = sum(1 for t in need_ex if cache.get(t))
            print(f"  ex [{i}/{len(need_ex)}] ok={ok}", flush=True)
        if i % 50 == 0:
            for w in words:
                if not looks_chinese(w.get("example_zh") or ""):
                    w["example_zh"] = cache.get((w.get("example_en") or "").strip(), "") or ""
            ex_ok = sum(1 for w in words if looks_chinese(w.get("example_zh") or ""))
            save_pack(words, def_ok, ex_ok)
            print(f"  checkpoint pack examples={ex_ok}/{len(words)}", flush=True)
        time.sleep(0.35)

    for w in words:
        if not looks_chinese(w.get("example_zh") or ""):
            w["example_zh"] = cache.get((w.get("example_en") or "").strip(), "") or ""

    def_ok = sum(1 for w in words if looks_chinese(w.get("def_zh") or ""))
    ex_ok = sum(1 for w in words if looks_chinese(w.get("example_zh") or ""))
    save_pack(words, def_ok, ex_ok)
    print(f"DONE defs={def_ok}/{len(words)} examples={ex_ok}/{len(words)}", flush=True)
    print(f"pack={PACK} size={PACK.stat().st_size/1024/1024:.2f}MB", flush=True)


if __name__ == "__main__":
    main()
