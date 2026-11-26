"""Step 3: search free media APIs with file A queries, fill demo_a1_20.deword images."""
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
FILE_A = ROOT / "packs" / "image_search_queries_demo20.json"
PACK = ROOT / "packs" / "demo_a1_20.deword"
WORK = ROOT / "_demo20_image_fill"
UA = "DeutschVocabImageBot/1.0 (offline vocab demo; contact: deutsch-local@example.com)"
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "").strip()
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
TARGET_W, TARGET_H = 640, 480
MIN_BYTES, MAX_BYTES = 12_000, 42_000


def opener():
    o = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    o.addheaders = [("User-Agent", UA)]
    return o


def fetch_json(url: str, op, timeout: int = 30, headers: dict | None = None) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        with op.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as e:
        print("  api err:", e)
        return None


def download_bytes(url: str, op, timeout: int = 40, referer: str = "") -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": referer or "https://commons.wikimedia.org/",
            },
        )
        with op.open(req, timeout=timeout) as resp:
            data = resp.read()
        return data if data and len(data) > 2000 else None
    except Exception as e:
        print("  dl err:", e)
        return None


def crop_webp(data: bytes, out: Path) -> bool:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        print("  decode err:", e)
        return False
    w, h = img.size
    target_ratio = 4 / 3
    cur = w / h
    if cur > target_ratio:
        nw = int(h * target_ratio)
        left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    else:
        nh = int(w / target_ratio)
        top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    out.parent.mkdir(parents=True, exist_ok=True)
    # Adaptive quality/size to land near 15–40KB; strip EXIF by re-encoding RGB only.
    best: bytes | None = None
    cropped = img
    for size in ((TARGET_W, TARGET_H), (560, 420), (480, 360)):
        scaled = cropped.resize(size, Image.Resampling.LANCZOS)
        for q in (48, 42, 36, 30, 24, 20, 16, 12):
            buf = io.BytesIO()
            scaled.save(buf, "WEBP", quality=q, method=6)
            blob = buf.getvalue()
            best = blob
            if MIN_BYTES <= len(blob) <= MAX_BYTES:
                out.write_bytes(best)
                return True
            if len(blob) <= MAX_BYTES and q <= 16:
                out.write_bytes(best)
                return True
    if not best:
        return False
    out.write_bytes(best)
    return out.exists() and out.stat().st_size > 1500


def recompress_existing(path: Path) -> bool:
    try:
        return crop_webp(path.read_bytes(), path)
    except Exception as e:
        print("  recompress err:", e)
        return False


def search_pixabay_urls(query: str, op) -> list[tuple[str, str]]:
    if not PIXABAY_KEY:
        return []
    params = {
        "key": PIXABAY_KEY,
        "q": query,
        "image_type": "photo",
        "safesearch": "true",
        "per_page": "8",
    }
    url = "https://pixabay.com/api/?" + urllib.parse.urlencode(params)
    data = fetch_json(url, op)
    out: list[tuple[str, str]] = []
    for hit in (data or {}).get("hits") or []:
        u = hit.get("webformatURL") or hit.get("largeImageURL") or hit.get("previewURL")
        if u:
            out.append((u, "pixabay"))
    return out


def search_pexels_urls(query: str, op) -> list[tuple[str, str]]:
    if not PEXELS_KEY:
        return []
    params = {"query": query, "per_page": "8"}
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(params)
    data = fetch_json(url, op, headers={"Authorization": PEXELS_KEY})
    out: list[tuple[str, str]] = []
    for photo in (data or {}).get("photos") or []:
        src = photo.get("src") or {}
        u = src.get("large") or src.get("medium") or src.get("original")
        if u:
            out.append((u, "pexels"))
    return out


def search_wikimedia_urls(query: str, op) -> list[tuple[str, str]]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": "10",
        "gsrnamespace": "6",
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": "800",
        "format": "json",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    data = fetch_json(url, op)
    pages = list((((data or {}).get("query") or {}).get("pages") or {}).values())
    cands: list[tuple[int, str, str]] = []
    for p in pages:
        infos = p.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = (info.get("mime") or "").lower()
        if not mime.startswith("image/") or mime in {"image/svg+xml", "image/gif"}:
            continue
        u = info.get("thumburl") or info.get("url")
        if not u:
            continue
        cands.append((info.get("size") or 0, u, "wikimedia"))
    cands.sort(key=lambda x: abs((x[0] or 200000) - 250000))
    return [(u, src) for _, u, src in cands[:6]]


def search_openverse_urls(query: str, op) -> list[tuple[str, str]]:
    params = {
        "q": query,
        "page_size": "8",
        "license_type": "commercial",
    }
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params)
    data = fetch_json(url, op, timeout=45)
    out: list[tuple[str, str]] = []
    for r in (data or {}).get("results") or []:
        u = r.get("url") or r.get("thumbnail")
        if u:
            out.append((u, "openverse"))
    return out


def find_and_download(query: str, op) -> tuple[bytes, str] | None:
    # Exact search_en only — do not rewrite/shorten queries.
    candidates: list[tuple[str, str]] = []
    candidates.extend(search_pixabay_urls(query, op))
    candidates.extend(search_pexels_urls(query, op))
    candidates.extend(search_openverse_urls(query, op))
    time.sleep(0.15)
    candidates.extend(search_wikimedia_urls(query, op))

    seen: set[str] = set()
    for url, source in candidates:
        if url in seen:
            continue
        seen.add(url)
        referer = {
            "pixabay": "https://pixabay.com/",
            "pexels": "https://www.pexels.com/",
            "openverse": "https://openverse.org/",
            "wikimedia": "https://commons.wikimedia.org/",
        }.get(source, "")
        data = download_bytes(url, op, referer=referer)
        if data:
            return data, source
        time.sleep(0.12)
    return None


def ensure_work_from_pack() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    need_extract = not (WORK / "words.json").exists() or not (WORK / "manifest.json").exists()
    if need_extract:
        with zipfile.ZipFile(PACK, "r") as zf:
            zf.extractall(WORK)
    else:
        # Keep existing images/; refresh words/manifest/audio from pack if missing audio.
        with zipfile.ZipFile(PACK, "r") as zf:
            for name in zf.namelist():
                if name.startswith("images/"):
                    continue
                dest = WORK / name
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(name))
    (WORK / "images").mkdir(parents=True, exist_ok=True)


def process_one(item: dict, out_path: Path) -> tuple[str, str | None, str]:
    """Return (word_id, source|None, message)."""
    wid = item["word_id"]
    query = item["search_en"]
    op = opener()
    if out_path.exists() and MIN_BYTES <= out_path.stat().st_size <= MAX_BYTES:
        return wid, item.get("image_source") or "existing", f"reuse {out_path.stat().st_size}B"
    if out_path.exists():
        if recompress_existing(out_path) and MIN_BYTES <= out_path.stat().st_size <= MAX_BYTES + 8000:
            return wid, item.get("image_source") or "existing", f"recompress {out_path.stat().st_size}B"
    hit = find_and_download(query, op)
    if not hit:
        return wid, None, "NO IMAGE"
    data, source = hit
    if not crop_webp(data, out_path):
        return wid, None, "convert failed"
    return wid, source, f"OK {source} {out_path.stat().st_size}B"


def main():
    file_a = json.loads(FILE_A.read_text(encoding="utf-8"))
    items = file_a["items"]
    ensure_work_from_pack()

    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    by_id = {w["id"]: w for w in words}
    img_dir = WORK / "images"

    print(f"proxy={PROXY} pixabay={'yes' if PIXABAY_KEY else 'no'} pexels={'yes' if PEXELS_KEY else 'no'}")
    print(f"items={len(items)}")

    results: dict[str, tuple[str | None, str]] = {}
    # Parallelize network-bound searches; keep modest workers to avoid API bans.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {
            ex.submit(process_one, item, img_dir / f"{item['word_id']}.webp"): item
            for item in items
        }
        for fut in concurrent.futures.as_completed(futs):
            item = futs[fut]
            wid, source, msg = fut.result()
            results[wid] = (source, msg)
            print(f"[{item['lemma_core']}] {item['search_en']} -> {msg}")

    ok = 0
    for item in items:
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
        src = source if source != "existing" else (item.get("image_source") or "wikimedia")
        w["image"] = {
            "path": rel,
            "source": src,
            "query_or_prompt": item["search_en"],
            "status": "ready",
            "attribution": src,
        }
        item["image_status"] = "ready"
        item["image_source"] = src
        ok += 1

    (WORK / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = 2
    manifest["title"] = "Demo A1 20"
    manifest["image_status"] = "filled" if ok == len(items) else f"partial:{ok}/{len(items)}"
    manifest["notes"] = "Images filled from Pixabay/Pexels/Openverse/Wikimedia using file A search_en"
    manifest["content_hash"] = hashlib.sha256((WORK / "words.json").read_bytes()).hexdigest()[:16]
    (WORK / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    FILE_A.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")

    if PACK.exists():
        PACK.unlink()
    with zipfile.ZipFile(PACK, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(WORK).as_posix())
    print(f"Done {PACK} images={ok}/{len(items)} size={PACK.stat().st_size/1024/1024:.2f}MB")


if __name__ == "__main__":
    main()
