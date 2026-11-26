"""Fix demo pack: ZH defs/examples + meaning images via proxy."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zh_defs_a1_demo import DEF_ZH

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "http://127.0.0.1:10809"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ[k] = PROXY

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
PACK = ROOT / "packs" / "demo_a1_100.deword"
WORK = ROOT / "_demo_fix_work"


def looks_chinese(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def proxy_opener():
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    opener.addheaders = [("User-Agent", "Mozilla/5.0 DeutschVocabFix/1.2")]
    return opener


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
        for attempt in range(2):
            try:
                time.sleep(0.8)
                out = tr.translate(text) or ""
                if looks_chinese(out) and out != text:
                    cache[text] = out
                    return out
            except Exception as e:
                print("  ex translate", type(tr).__name__, type(e).__name__)
                time.sleep(1.5)
    cache[text] = out if looks_chinese(out) else ""
    return cache[text]


def concrete_prompt(lemma: str, def_en: str, example_de: str) -> str:
    base = re.sub(r"^(der|die|das)\s+", "", lemma.split(",")[0], flags=re.I).strip()
    mapping = {
        "über": "airplane flying above a person looking up, realistic photo, no text",
        "unter": "cat sitting under a wooden table, realistic photo, no text",
        "auf": "open book lying on a wooden table, realistic photo, no text",
        "in": "person entering a room through a doorway, realistic photo, no text",
        "an": "framed picture hanging on a wall, realistic photo, no text",
        "mit": "two friends walking side by side, realistic photo, no text",
        "von": "hand taking a letter from a mailbox, realistic photo, no text",
        "für": "gift box with ribbon on a table, realistic photo, no text",
        "kein": "empty white plate on table meaning none, realistic photo, no text",
        "nicht": "person shaking head saying no, realistic photo, no text",
        "und": "two people shaking hands, realistic photo, no text",
        "oder": "forked path left or right choice, realistic photo, no text",
        "aber": "sunny half and rainy half contrast sky, realistic photo, no text",
        "der": "adult man standing outdoors, realistic photo, no text",
        "die": "adult woman standing outdoors, realistic photo, no text",
        "das": "young child playing with toys, realistic photo, no text",
        "Tisch": "wooden dining table in kitchen, realistic photo, no text",
        "Haus": "suburban house exterior daytime, realistic photo, no text",
        "Buch": "open book on desk, realistic photo, no text",
        "Auto": "car parked on street, realistic photo, no text",
        "Wasser": "clear glass of water, realistic photo, no text",
        "Apfel": "red apple on wooden table, realistic photo, no text",
        "Schule": "school building exterior, realistic photo, no text",
        "Kind": "smiling child outdoors, realistic photo, no text",
        "Mann": "adult man portrait photo, no text",
        "Frau": "adult woman portrait photo, no text",
        "Zeit": "analog wall clock, realistic photo, no text",
        "Tag": "bright sunny day landscape, realistic photo, no text",
        "jetzt": "wristwatch close-up meaning now, realistic photo, no text",
        "hier": "map pin marking here, realistic photo, no text",
        "da": "person pointing into distance, realistic photo, no text",
        "jetzt": "modern wristwatch close up, realistic photo, no text",
        "Jahr": "calendar page showing a year, realistic photo, no text",
        "Beispiel": "chalkboard with example illustration, realistic photo, no text",
        "Mensch": "diverse people in a city street, realistic photo, no text",
        "Frau": "woman smiling portrait, realistic photo, no text",
    }
    if base in mapping:
        return mapping[base]
    gloss = (def_en or "").split(",")[0].strip()
    if gloss:
        return f"realistic photo clearly illustrating: {gloss}, single subject, no text, no watermark"
    return f"realistic photo for concept {base}, no text, no watermark"


def _keywords(prompt: str) -> list[str]:
    stop = {"realistic", "photo", "no", "text", "watermark", "clear", "subject", "single", "illustrating", "meaning", "concept", "for", "the", "a", "an", "and", "with", "on", "in", "of", "to"}
    words = re.findall(r"[A-Za-z]{3,}", prompt.lower())
    keys = [w for w in words if w not in stop]
    return keys[:3] or ["object"]


def download_image(prompt: str, opener) -> Image.Image | None:
    """Try free image sources (pollinations may 402)."""
    keys = _keywords(prompt)
    tag = ",".join(urllib.parse.quote(k) for k in keys)
    seed = abs(hash(prompt)) % 10000
    urls = [
        f"https://loremflickr.com/640/480/{tag}?lock={seed}",
        f"https://loremflickr.com/640/480/{keys[0]}?lock={seed}",
        f"https://picsum.photos/seed/{seed}/640/480",  # last resort unrelated photo
    ]
    for url in urls:
        try:
            with opener.open(url, timeout=25) as resp:
                data = resp.read()
            if len(data) < 5000:
                continue
            return Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:
            print("  img err:", e)
            continue
    return None


def fallback_scene(prompt: str, def_zh: str) -> Image.Image:
    w, h = 768, 512
    img = Image.new("RGB", (w, h), (236, 244, 252))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w, 280), fill=(135, 190, 235))
    draw.rectangle((0, 280, w, h), fill=(120, 170, 110))
    pl = prompt.lower()
    if "plane" in pl or "above" in pl or "über" in pl:
        draw.polygon([(160, 110), (300, 130), (160, 150), (190, 130)], fill=(245, 245, 245))
        draw.ellipse((340, 330, 410, 410), fill=(70, 70, 70))
        draw.rectangle((360, 410, 390, 500), fill=(50, 50, 80))
    elif "table" in pl:
        draw.rectangle((220, 300, 560, 340), fill=(160, 110, 60))
        draw.rectangle((250, 340, 280, 450), fill=(120, 80, 40))
        draw.rectangle((500, 340, 530, 450), fill=(120, 80, 40))
    elif "book" in pl:
        draw.rectangle((280, 200, 500, 420), fill=(250, 250, 250))
        draw.line((390, 200, 390, 420), fill=(200, 60, 60), width=4)
    else:
        draw.ellipse((300, 160, 480, 340), fill=(255, 255, 255))
    try:
        font = ImageFont.truetype("msyh.ttc", 34)
    except Exception:
        font = ImageFont.load_default()
    draw.rounded_rectangle((40, 420, 720, 500), radius=16, fill=(255, 255, 255))
    draw.text((60, 445), (def_zh or "")[:22], fill=(20, 20, 20), font=font)
    return img


def main():
    translators = make_translators()
    opener = proxy_opener()

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    with zipfile.ZipFile(PACK, "r") as zf:
        zf.extractall(WORK)

    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    ex_cache: dict[str, str] = {}
    ok_img = 0

    # Pre-translate unique examples first (fewer API calls)
    unique_ex = sorted({(w.get("example_en") or "").strip() for w in words if (w.get("example_en") or "").strip()})
    print(f"Translating {len(unique_ex)} unique examples…")
    for j, ex in enumerate(unique_ex, 1):
        zh = translate_example(ex, ex_cache, translators)
        print(f"  ex[{j}/{len(unique_ex)}] zh={bool(zh)} {ex[:50]}")

    for i, w in enumerate(words, 1):
        def_en = w.get("def_en") or ""
        ex_en = w.get("example_en") or ""
        w["def_zh"] = zh_def(def_en)
        w["example_zh"] = translate_example(ex_en, ex_cache, translators)

        prompt = concrete_prompt(w.get("lemma", ""), def_en, w.get("example_de") or "")
        img_rel = w["image"]["path"]
        img_path = WORK / img_rel
        img = download_image(prompt, opener)
        if img is None:
            img = fallback_scene(prompt, w["def_zh"])
            source = "fallback_scene"
        else:
            source = "ai_web"
            ok_img += 1
        img = img.resize((640, 480), Image.Resampling.LANCZOS)
        img_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(img_path, "WEBP", quality=48, method=6)
        w["image"] = {"path": img_rel, "source": source, "query_or_prompt": prompt}
        print(
            f"[{i}/{len(words)}] {w['lemma'][:28]} | {w['def_zh'][:16]} | exZH={bool(w['example_zh'])} | {source}"
        )

    (WORK / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = 4
    manifest["notes"] = "ZH defs dictionary + translated examples; meaning images via proxy"
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
    print(f"Done {PACK} ai_images={ok_img}/{len(words)} MB={PACK.stat().st_size/1024/1024:.2f}")


if __name__ == "__main__":
    main()
