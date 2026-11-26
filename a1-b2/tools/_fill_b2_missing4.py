"""Quick-fill 4 missing B2 images via Pixabay (better queries) + Wikimedia."""
from __future__ import annotations

import io
import json
import os
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
WORK = ROOT / "_b2_pack_work"
PACK = ROOT / "packs" / "demo_b2.deword"
FILE_A = ROOT / "packs" / "image_search_queries_b2.json"
KEYS = json.loads((ROOT / "packs" / "image_api_keys.json").read_text(encoding="utf-8"))
PIXABAY = str(KEYS.get("PIXABAY_API_KEY") or "").strip()
PROXY = "http://127.0.0.1:10809"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ[k] = PROXY
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TARGET = [(640, 480), (560, 420), (480, 360)]
MIN_B, MAX_B = 12_000, 42_000

MISSING = [
    ("b2_4336_1679807421031", "person tearing paper angrily"),
    ("b2_4868_1679807421563", "two friends handshake hometown reunion"),
    ("b2_4873_1679807421568", "open space room flexibility freedom"),
    ("b2_4979_1679807421674", "inclined slope hill tendency"),
]


def opener():
    o = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    o.addheaders = [("User-Agent", UA)]
    return o


def fetch_json(url: str, op, headers: dict | None = None) -> dict | None:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with op.open(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                wait = 20 + attempt * 15
                print(f"  HTTP {e.code} sleep {wait}s", flush=True)
                time.sleep(wait)
                continue
            print(f"  api err {e}", flush=True)
            return None
        except Exception as e:
            print(f"  api err {type(e).__name__}: {e}", flush=True)
            time.sleep(2)
    return None


def download(url: str, op, referer: str) -> bytes | None:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Referer": referer, "Accept": "image/*,*/*;q=0.8"}
        )
        with op.open(req, timeout=30) as resp:
            data = resp.read()
        return data if data and len(data) > 2000 else None
    except Exception as e:
        print(f"  dl err {type(e).__name__}: {e}", flush=True)
        return None


def crop_webp(data: bytes, out: Path) -> bool:
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        print(f"  decode {e}", flush=True)
        return False
    w, h = img.size
    ratio = 4 / 3
    if w / h > ratio:
        nw = int(h * ratio)
        left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    else:
        nh = int(w / ratio)
        top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    best = None
    for size in TARGET:
        scaled = img.resize(size, Image.Resampling.LANCZOS)
        for q in (48, 42, 36, 30, 24, 20, 16, 12):
            buf = io.BytesIO()
            scaled.save(buf, "WEBP", quality=q, method=6)
            best = buf.getvalue()
            if MIN_B <= len(best) <= MAX_B:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(best)
                return True
    if not best:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(best)
    return out.exists() and out.stat().st_size > 1500


def pixabay(query: str, op) -> list[tuple[str, str]]:
    if not PIXABAY:
        return []
    url = "https://pixabay.com/api/?" + urllib.parse.urlencode(
        {
            "key": PIXABAY,
            "q": query,
            "image_type": "photo",
            "safesearch": "true",
            "per_page": "10",
        }
    )
    data = fetch_json(url, op)
    out = []
    for hit in (data or {}).get("hits") or []:
        u = hit.get("webformatURL") or hit.get("largeImageURL")
        if u:
            out.append((u, "pixabay"))
    return out


def wikimedia(query: str, op) -> list[tuple[str, str]]:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"filetype:bitmap {query}",
            "gsrlimit": "12",
            "gsrnamespace": "6",
            "prop": "imageinfo",
            "iiprop": "url|mime|size",
            "iiurlwidth": "800",
            "format": "json",
            "origin": "*",
        }
    )
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
            cands.append((u, "wikimedia"))
    return cands


def find_one(query: str, op) -> tuple[bytes, str] | None:
    # Prefer Wikimedia first (avoid Pixabay 429)
    for url, src in wikimedia(query, op) + pixabay(query, op):
        referer = (
            "https://commons.wikimedia.org/"
            if src == "wikimedia"
            else "https://pixabay.com/"
        )
        data = download(url, op, referer)
        if data:
            return data, src
        time.sleep(0.3)
    return None


def main() -> None:
    op = opener()
    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    by_id = {w["id"]: w for w in words}
    file_a = json.loads(FILE_A.read_text(encoding="utf-8"))
    by_a = {it["word_id"]: it for it in file_a["items"]}
    ok = 0
    for wid, query in MISSING:
        print(f"{wid} <- {query}", flush=True)
        out = WORK / "images" / f"{wid}.webp"
        hit = find_one(query, op)
        if not hit:
            print("  FAIL", flush=True)
            continue
        data, src = hit
        if not crop_webp(data, out):
            print("  convert fail", flush=True)
            continue
        print(f"  OK {src} {out.stat().st_size}B", flush=True)
        rel = f"images/{wid}.webp"
        w = by_id[wid]
        w["image"] = {
            "path": rel,
            "source": src,
            "query_or_prompt": query,
            "status": "ready",
            "attribution": src,
        }
        it = by_a.get(wid)
        if it:
            it["search_en"] = query
            it["image_status"] = "ready"
            it["image_source"] = src
        ok += 1
        time.sleep(1.2)

    (WORK / "words.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    FILE_A.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")
    # also dump patch for re-apply after repair overwrite
    patch = {wid: by_id[wid]["image"] for wid, _ in MISSING if by_id[wid].get("image", {}).get("status") == "ready"}
    (WORK / "_missing4_image_patch.json").write_text(
        json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ready = sum(1 for w in words if (w.get("image") or {}).get("status") == "ready")
    print(f"filled {ok}/4 ready_now={ready}/{len(words)}", flush=True)


if __name__ == "__main__":
    main()
