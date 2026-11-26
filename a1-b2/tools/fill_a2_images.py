"""Fill demo_a2.deword images: Pixabay/Pexels -> Wikimedia. Stop after 10 consecutive fails."""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "http://127.0.0.1:10809"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ[k] = PROXY

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
FILE_A = ROOT / "packs" / "image_search_queries_a2.json"
PACK = ROOT / "packs" / "demo_a2.deword"
KEYS_FILE = ROOT / "packs" / "image_api_keys.json"
WORK = ROOT / "_a2_pack_work"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TARGET_W, TARGET_H = 640, 480
MIN_BYTES, MAX_BYTES = 12_000, 42_000
MAX_CONSEC_FAIL = 10
PIXABAY_KEY = ""
PEXELS_KEY = ""


def load_keys() -> tuple[str, str]:
    pixabay = (os.environ.get("PIXABAY_API_KEY") or "").strip()
    pexels = (os.environ.get("PEXELS_API_KEY") or "").strip()
    if KEYS_FILE.exists():
        data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        pixabay = pixabay or str(data.get("PIXABAY_API_KEY") or "").strip()
        pexels = pexels or str(data.get("PEXELS_API_KEY") or "").strip()
    if pixabay.startswith("paste_"):
        pixabay = ""
    if pexels.startswith("paste_"):
        pexels = ""
    return pixabay, pexels


def opener():
    o = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    o.addheaders = [("User-Agent", UA)]
    return o


def fetch_json(url: str, op, timeout: int = 35, headers: dict | None = None) -> dict | None:
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with op.open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                wait = 45 + attempt * 20
                print(f"  api HTTP {e.code}, sleep {wait}s")
                time.sleep(wait)
                continue
            print("  api err:", e)
            return None
        except Exception as e:
            print("  api err:", e)
            return None
    return None


def download_bytes(url: str, op, timeout: int = 45, referer: str = "") -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "image/*,*/*;q=0.8",
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
    ratio = 4 / 3
    cur = w / h
    if cur > ratio:
        nw = int(h * ratio)
        left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    else:
        nh = int(w / ratio)
        top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    best = None
    for size in ((TARGET_W, TARGET_H), (560, 420), (480, 360)):
        scaled = img.resize(size, Image.Resampling.LANCZOS)
        for q in (48, 42, 36, 30, 24, 20, 16, 12):
            buf = io.BytesIO()
            scaled.save(buf, "WEBP", quality=q, method=6)
            blob = buf.getvalue()
            best = blob
            if MIN_BYTES <= len(blob) <= MAX_BYTES:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(best)
                return True
            if len(blob) <= MAX_BYTES and q <= 16:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(best)
                return True
    if not best:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(best)
    return out.exists() and out.stat().st_size > 1500


def search_pixabay(query: str, op) -> list[tuple[str, str]]:
    if not PIXABAY_KEY:
        return []
    params = {
        "key": PIXABAY_KEY,
        "q": query,
        "image_type": "photo",
        "safesearch": "true",
        "per_page": "10",
    }
    url = "https://pixabay.com/api/?" + urllib.parse.urlencode(params)
    data = fetch_json(url, op)
    out = []
    for hit in (data or {}).get("hits") or []:
        u = hit.get("webformatURL") or hit.get("largeImageURL") or hit.get("previewURL")
        if u:
            out.append((u, "pixabay"))
    return out


def search_pexels(query: str, op) -> list[tuple[str, str]]:
    if not PEXELS_KEY:
        return []
    params = {"query": query, "per_page": "10"}
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(params)
    data = fetch_json(url, op, headers={"Authorization": PEXELS_KEY})
    out = []
    for photo in (data or {}).get("photos") or []:
        src = photo.get("src") or {}
        u = src.get("large") or src.get("medium") or src.get("original")
        if u:
            out.append((u, "pexels"))
    return out


def search_wikimedia(query: str, op) -> list[tuple[str, str]]:
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
        "origin": "*",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    data = fetch_json(url, op)
    pages = list((((data or {}).get("query") or {}).get("pages") or {}).values())
    cands = []
    for p in pages:
        infos = p.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = (info.get("mime") or "").lower()
        if not mime.startswith("image/") or mime in {"image/svg+xml", "image/gif"}:
            continue
        u = info.get("thumburl") or info.get("url")
        if u:
            cands.append((info.get("size") or 0, u, "wikimedia"))
    cands.sort(key=lambda x: abs((x[0] or 200000) - 250000))
    return [(u, src) for _, u, src in cands[:8]]


def find_and_download(query: str, op) -> tuple[bytes, str] | None:
    candidates = []
    candidates.extend(search_pixabay(query, op))
    time.sleep(0.12)
    candidates.extend(search_pexels(query, op))
    time.sleep(0.12)
    # Only hit Wikimedia if keyed sources empty
    if not candidates:
        candidates.extend(search_wikimedia(query, op))

    seen = set()
    for url, source in candidates:
        if url in seen:
            continue
        seen.add(url)
        referer = {
            "pixabay": "https://pixabay.com/",
            "pexels": "https://www.pexels.com/",
            "wikimedia": "https://commons.wikimedia.org/",
        }.get(source, "")
        data = download_bytes(url, op, referer=referer)
        if data:
            return data, source
        time.sleep(0.1)
    # last resort wikimedia even if pixabay returned undownloadable urls
    for url, source in search_wikimedia(query, op):
        if url in seen:
            continue
        data = download_bytes(url, op, referer="https://commons.wikimedia.org/")
        if data:
            return data, source
    return None


def save_progress(file_a, words, sources_count, ok, total, stopped_reason: str = ""):
    (WORK / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = max(int(manifest.get("version") or 1), 2)
    manifest["title"] = "Demo A2"
    manifest["pack_id"] = "demo_a2"
    manifest["level"] = "A2"
    manifest["word_count"] = len(words)
    manifest["image_status"] = "filled" if ok == total else f"partial:{ok}/{total}"
    if stopped_reason:
        manifest["stopped_reason"] = stopped_reason
    manifest["notes"] = "A2 images via Pixabay/Pexels + Wikimedia; same pipeline as demo_a1_100"
    manifest["query_file"] = "image_search_queries_a2.json"
    manifest["image_sources"] = sources_count
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
    print(f"Saved {PACK} images={ok}/{total} size={PACK.stat().st_size/1024/1024:.2f}MB sources={sources_count}")


def main():
    global PIXABAY_KEY, PEXELS_KEY
    PIXABAY_KEY, PEXELS_KEY = load_keys()

    if not FILE_A.exists() or not (WORK / "words.json").exists():
        raise SystemExit("Run build_a2_pack_skeleton.py first")

    file_a = json.loads(FILE_A.read_text(encoding="utf-8"))
    items = file_a["items"]
    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    by_id = {w["id"]: w for w in words}
    img_dir = WORK / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    op = opener()

    print(f"proxy={PROXY} pixabay={'yes' if PIXABAY_KEY else 'NO'} pexels={'yes' if PEXELS_KEY else 'NO'}")
    print(f"items={len(items)} stop_after_consec_fail={MAX_CONSEC_FAIL}")

    ok = 0
    consec_fail = 0
    sources_count: dict[str, int] = {}
    stopped_reason = ""

    # resume: skip already ready with matching query + file
    for i, item in enumerate(items, 1):
        wid = item["word_id"]
        query = item["search_en"]
        out = img_dir / f"{wid}.webp"
        w = by_id.get(wid)
        print(f"[{i}/{len(items)}] {item.get('lemma_core') or item['lemma'][:24]} <- {query}")

        if not w:
            print("  missing word")
            item["image_status"] = "pending"
            consec_fail += 1
            if consec_fail >= MAX_CONSEC_FAIL:
                stopped_reason = f"stopped: {MAX_CONSEC_FAIL} consecutive failures at {i}"
                print(stopped_reason)
                break
            continue

        existing = w.get("image") or {}
        if (
            item.get("image_status") == "ready"
            and existing.get("status") == "ready"
            and existing.get("query_or_prompt") == query
            and out.exists()
            and out.stat().st_size > 1500
        ):
            src = existing.get("source") or "existing"
            print(f"  reuse {out.stat().st_size}B ({src})")
            sources_count[src] = sources_count.get(src, 0) + 1
            ok += 1
            consec_fail = 0
            continue

        if out.exists():
            out.unlink()
        hit = find_and_download(query, op)
        if not hit:
            print("  NO IMAGE")
            item["image_status"] = "pending"
            w["image"] = {
                "path": "",
                "source": "",
                "query_or_prompt": query,
                "status": "pending",
            }
            consec_fail += 1
            if consec_fail >= MAX_CONSEC_FAIL:
                stopped_reason = f"stopped: {MAX_CONSEC_FAIL} consecutive search failures at {i}"
                print(stopped_reason)
                break
            time.sleep(0.5)
            continue

        data, source = hit
        if not crop_webp(data, out):
            print("  convert failed")
            item["image_status"] = "pending"
            consec_fail += 1
            if consec_fail >= MAX_CONSEC_FAIL:
                stopped_reason = f"stopped: {MAX_CONSEC_FAIL} consecutive failures at {i}"
                print(stopped_reason)
                break
            continue

        print(f"  OK {source} {out.stat().st_size}B")
        consec_fail = 0
        rel = f"images/{wid}.webp"
        w["image"] = {
            "path": rel,
            "source": source,
            "query_or_prompt": query,
            "status": "ready",
            "attribution": source,
        }
        item["image_status"] = "ready"
        item["image_source"] = source
        sources_count[source] = sources_count.get(source, 0) + 1
        ok += 1
        # checkpoint every 25
        if ok % 25 == 0:
            save_progress(file_a, words, sources_count, ok, len(items), "")
        time.sleep(0.65)

    save_progress(file_a, words, sources_count, ok, len(items), stopped_reason)
    print("DONE" + (" early stop" if stopped_reason else " full pass"))


if __name__ == "__main__":
    main()
