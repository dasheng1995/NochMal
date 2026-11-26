"""Generate minimal flat vector illustrations for demo_a1_20 (separate from photo pack).

Preserves:
  - packs/demo_a1_20.deword / demo_a1_20_photo.deword  (photo search version)
  - tools/fill_demo20_images.py / fill_demo20_images_photo.py

Produces:
  - packs/demo_a1_20_flat.deword
  - packs/image_search_queries_demo20_flat.json  (file A status for flat run)
  - _demo20_flat_fill/  work directory
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import os
import shutil
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "http://127.0.0.1:10809"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ[k] = PROXY

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
FILE_A_SRC = ROOT / "packs" / "image_search_queries_demo20.json"
FILE_A_FLAT = ROOT / "packs" / "image_search_queries_demo20_flat.json"
PHOTO_PACK = ROOT / "packs" / "demo_a1_20_photo.deword"
FALLBACK_PACK = ROOT / "packs" / "demo_a1_20.deword"
OUT_PACK = ROOT / "packs" / "demo_a1_20_flat.deword"
WORK = ROOT / "_demo20_flat_fill"
RAW = WORK / "_raw"
UA = "DeutschVocabFlatBot/1.0 (offline vocab demo; contact: deutsch-local@example.com)"

STYLE = (
    "flat 2D vector clipart, minimal flat design illustration, pure white background, "
    "thick clean outline strokes, solid pastel flat color fills only, "
    "no gradient, no shadow, no 3D, no photorealism, no texture, no text, no watermark"
)
TARGET_W, TARGET_H = 640, 480
MIN_BYTES, MAX_BYTES = 12_000, 42_000
# Anonymous Pollinations: ~1 new image / 45s. Stay polite.
REQUEST_GAP_SEC = 48
MAX_RETRIES = 6


def opener():
    o = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    o.addheaders = [("User-Agent", UA)]
    return o


def build_prompt(search_en: str) -> str:
    # Exact search_en scene + fixed style suffix — do not rewrite the keyword itself.
    return f"{STYLE}, scene: {search_en}"


def pollinations_url(search_en: str, seed: int) -> str:
    prompt = build_prompt(search_en)
    encoded = urllib.parse.quote(prompt, safe="")
    qs = urllib.parse.urlencode(
        {
            "width": "768",
            "height": "576",
            "nologo": "true",
            "enhance": "false",
            "seed": str(seed),
        }
    )
    return f"https://image.pollinations.ai/prompt/{encoded}?{qs}"


def download_bytes(url: str, op, timeout: int = 120) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
        with op.open(req, timeout=timeout) as resp:
            data = resp.read()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "image" not in ctype and (not data or data[:1] in (b"{", b"<")):
            print("  non-image response")
            return None
        return data if data and len(data) > 2000 else None
    except urllib.error.HTTPError as e:
        retry_after = e.headers.get("Retry-After") if e.headers else None
        print(f"  dl HTTP {e.code} retry_after={retry_after}")
        wait = int(retry_after) if retry_after and str(retry_after).isdigit() else REQUEST_GAP_SEC
        if e.code in (402, 429):
            time.sleep(wait)
        return None
    except Exception as e:
        print("  dl err:", e)
        return None


def scrub_logo(img: Image.Image) -> Image.Image:
    """Cover common pollinations watermark corner with white."""
    from PIL import ImageDraw

    w, h = img.size
    draw = ImageDraw.Draw(img)
    draw.rectangle([int(w * 0.70), int(h * 0.86), w, h], fill=(255, 255, 255))
    return img


def to_webp(data: bytes, out: Path) -> bool:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        print("  decode err:", e)
        return False
    img = scrub_logo(img)
    w, h = img.size
    ratio = 4 / 3
    cur = w / h
    if abs(cur - ratio) > 0.02:
        if cur > ratio:
            nw = int(h * ratio)
            left = (w - nw) // 2
            img = img.crop((left, 0, left + nw, h))
        else:
            nh = int(w / ratio)
            top = (h - nh) // 2
            img = img.crop((0, top, w, top + nh))
    img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    best: bytes | None = None
    for q in (48, 42, 36, 30, 24, 20, 16, 12):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=q, method=6)
        blob = buf.getvalue()
        best = blob
        if MIN_BYTES <= len(blob) <= MAX_BYTES:
            break
        if len(blob) <= MAX_BYTES and q <= 16:
            break
    if not best:
        return False
    out.write_bytes(best)
    return out.exists() and out.stat().st_size > 1500


def ensure_work() -> None:
    if WORK.exists():
        # Keep raw/generated images across reruns; refresh non-image pack files.
        pass
    WORK.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    src = PHOTO_PACK if PHOTO_PACK.exists() else FALLBACK_PACK
    with zipfile.ZipFile(src, "r") as zf:
        for name in zf.namelist():
            if name.startswith("images/"):
                continue
            dest = WORK / name
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(name))
    (WORK / "images").mkdir(parents=True, exist_ok=True)


def process_one(item: dict) -> tuple[str, str | None, str]:
    wid = item["word_id"]
    query = item["search_en"]
    out = WORK / "images" / f"{wid}.webp"
    raw = RAW / f"{wid}.jpg"
    if out.exists() and MIN_BYTES <= out.stat().st_size <= MAX_BYTES + 5000:
        return wid, "pollinations_flat", f"reuse {out.stat().st_size}B"

    op = opener()
    seed = abs(hash(wid)) % 1_000_000
    url = pollinations_url(query, seed)
    data = download_bytes(url, op)
    if not data:
        # one retry with different seed
        time.sleep(1.0)
        data = download_bytes(pollinations_url(query, seed + 17), op)
    if not data:
        return wid, None, "NO IMAGE"
    raw.write_bytes(data)
    if not to_webp(data, out):
        return wid, None, "convert failed"
    return wid, "pollinations_flat", f"OK {out.stat().st_size}B"


def main():
    src_a = json.loads(FILE_A_SRC.read_text(encoding="utf-8"))
    # Independent flat status file — do not overwrite photo file A statuses.
    file_a = json.loads(json.dumps(src_a))
    file_a["pack_id"] = "demo_a1_20_flat"
    file_a["rules"] = {
        **(file_a.get("rules") or {}),
        "style": STYLE,
        "generator": "pollinations",
        "next_agent": "Use search_en + flat style prompt; write images/ and pack demo_a1_20_flat.deword",
    }
    for item in file_a["items"]:
        item["image_status"] = "pending"
        item.pop("image_source", None)

    ensure_work()
    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    by_id = {w["id"]: w for w in words}

    print(f"proxy={PROXY}")
    print(f"style={STYLE[:60]}...")
    print(f"items={len(file_a['items'])} -> {OUT_PACK.name}")

    results: dict[str, tuple[str | None, str]] = {}
    # Keep concurrency modest — Pollinations rate-limits aggressive fans.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(process_one, item): item for item in file_a["items"]}
        for fut in concurrent.futures.as_completed(futs):
            item = futs[fut]
            wid, source, msg = fut.result()
            results[wid] = (source, msg)
            print(f"[{item['lemma_core']}] {item['search_en']} -> {msg}")

    ok = 0
    for item in file_a["items"]:
        wid = item["word_id"]
        source, msg = results.get(wid, (None, "missing"))
        rel = f"images/{wid}.webp"
        path = WORK / rel
        if not path.exists() or source is None:
            item["image_status"] = "pending"
            continue
        w = by_id.get(wid)
        if not w:
            item["image_status"] = "pending"
            continue
        prompt = build_prompt(item["search_en"])
        w["image"] = {
            "path": rel,
            "source": source,
            "query_or_prompt": prompt,
            "status": "ready",
            "attribution": "pollinations.ai flat vector",
        }
        item["image_status"] = "ready"
        item["image_source"] = source
        item["image_prompt"] = prompt
        ok += 1

    (WORK / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = 3
    manifest["title"] = "Demo A1 20 Flat"
    manifest["pack_id"] = "demo_a1_20_flat"
    manifest["image_status"] = "filled" if ok == len(file_a["items"]) else f"partial:{ok}/{len(file_a['items'])}"
    manifest["notes"] = (
        "Flat vector illustrations generated from file A search_en "
        "(minimal flat vector, white bg, clean lines). Photo pack kept separately."
    )
    manifest["image_style"] = STYLE
    manifest["content_hash"] = hashlib.sha256((WORK / "words.json").read_bytes()).hexdigest()[:16]
    (WORK / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    FILE_A_FLAT.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")

    if OUT_PACK.exists():
        OUT_PACK.unlink()
    with zipfile.ZipFile(OUT_PACK, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file() and "_raw" not in path.parts:
                zf.write(path, path.relative_to(WORK).as_posix())
    print(f"Done {OUT_PACK} images={ok}/{len(file_a['items'])} size={OUT_PACK.stat().st_size/1024/1024:.2f}MB")
    print(f"Photo pack preserved: {PHOTO_PACK if PHOTO_PACK.exists() else FALLBACK_PACK}")


if __name__ == "__main__":
    main()
