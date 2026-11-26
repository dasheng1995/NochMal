"""Benchmark free image sources for ~5000 vocab images.

Measures: success, latency, bytes, whether keyword-aware, rate-limit signals.
Uses proxy http://127.0.0.1:10809
"""
from __future__ import annotations

import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

PROXY = os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:10809"
for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ[k] = PROXY

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
OUT_DIR = ROOT / "packs" / "_bench_images"
OUT_JSON = ROOT / "packs" / "image_source_bench.json"
UA = "DeutschVocabBench/1.0 (feasibility test; local demo)"
QUERY = "hand holding book"
STYLE = (
    "flat 2D vector clipart, minimal flat design, pure white background, "
    "thick clean outlines, solid pastel fills, no 3D, no shadow, no text"
)


def opener():
    o = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    )
    o.addheaders = [("User-Agent", UA)]
    return o


def timed(fn):
    t0 = time.perf_counter()
    err = None
    data = None
    meta = {}
    try:
        data, meta = fn()
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
    ms = int((time.perf_counter() - t0) * 1000)
    return {"ok": data is not None and len(data) > 1500, "ms": ms, "bytes": len(data or b""), "error": err, **meta}, data


def save(name: str, data: bytes | None):
    if not data:
        return None
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    path.write_bytes(data)
    return str(path)


# ---------- providers ----------

def pollinations(op, attempt: int = 0):
    prompt = f"{STYLE}, scene: {QUERY}"
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt, safe="")
        + "?"
        + urllib.parse.urlencode(
            {"width": "640", "height": "480", "nologo": "true", "seed": str(100 + attempt)}
        )
    )

    def run():
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
        try:
            with op.open(req, timeout=90) as resp:
                body = resp.read()
                return body, {"provider": "pollinations", "status": resp.status, "ctype": resp.headers.get("Content-Type")}
        except urllib.error.HTTPError as e:
            retry = e.headers.get("Retry-After") if e.headers else None
            body = e.read() if hasattr(e, "read") else b""
            raise RuntimeError(f"HTTP {e.code} retry_after={retry} body={body[:120]!r}") from e

    return timed(run)


def wikimedia(op):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {QUERY}",
        "gsrlimit": "5",
        "gsrnamespace": "6",
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": "800",
        "format": "json",
    }
    api = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)

    def run():
        with op.open(api, timeout=40) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        pages = list((((data or {}).get("query") or {}).get("pages") or {}).values())
        url = None
        for p in pages:
            infos = p.get("imageinfo") or []
            if not infos:
                continue
            info = infos[0]
            mime = (info.get("mime") or "").lower()
            if not mime.startswith("image/") or "svg" in mime or "gif" in mime:
                continue
            url = info.get("thumburl") or info.get("url")
            if url:
                break
        if not url:
            raise RuntimeError("no wikimedia candidate")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": UA, "Referer": "https://commons.wikimedia.org/"},
        )
        with op.open(req, timeout=40) as resp:
            return resp.read(), {"provider": "wikimedia", "image_url": url}

    return timed(run)


def openverse(op):
    params = {"q": QUERY, "page_size": "5", "license_type": "commercial"}
    api = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params)

    def run():
        with op.open(api, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
        results = (data or {}).get("results") or []
        if not results:
            raise RuntimeError("no openverse results")
        url = results[0].get("url") or results[0].get("thumbnail")
        if not url:
            raise RuntimeError("empty openverse url")
        req = urllib.request.Request(
            url, headers={"User-Agent": UA, "Referer": "https://openverse.org/"}
        )
        with op.open(req, timeout=45) as resp:
            return resp.read(), {"provider": "openverse", "image_url": url}

    return timed(run)


def huggingface_inference(op):
    # Public inference without token usually fails; measure anyway.
    model = "black-forest-labs/FLUX.1-schnell"
    url = f"https://api-inference.huggingface.co/models/{model}"

    def run():
        body = json.dumps({"inputs": f"{STYLE}, {QUERY}"}).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "image/*"},
            method="POST",
        )
        with op.open(req, timeout=60) as resp:
            return resp.read(), {"provider": "hf_inference", "status": resp.status, "ctype": resp.headers.get("Content-Type")}

    return timed(run)


def together_try(op):
    url = "https://api.together.xyz/v1/images/generations"

    def run():
        body = json.dumps(
            {
                "model": "black-forest-labs/FLUX.1-schnell",
                "prompt": f"{STYLE}, {QUERY}",
                "width": 640,
                "height": 480,
            }
        ).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"User-Agent": UA, "Content-Type": "application/json"},
            method="POST",
        )
        with op.open(req, timeout=30) as resp:
            return resp.read(), {"provider": "together", "status": resp.status}

    return timed(run)


def local_flat_svg_raster():
    """Deterministic free/local flat illustration (no network)."""

    def run():
        # Simple flat scene approximating "hand holding book"
        img = Image.new("RGB", (640, 480), (255, 255, 255))
        d = ImageDraw.Draw(img)
        # book
        d.rectangle([180, 140, 420, 340], fill=(90, 156, 255), outline=(30, 30, 30), width=4)
        d.rectangle([300, 140, 420, 340], fill=(120, 180, 255), outline=(30, 30, 30), width=4)
        # pages line
        d.line([300, 140, 300, 340], fill=(30, 30, 30), width=3)
        # hand (simple shapes)
        d.ellipse([360, 280, 520, 420], fill=(255, 204, 170), outline=(30, 30, 30), width=4)
        d.rectangle([400, 250, 480, 310], fill=(255, 204, 170), outline=(30, 30, 30), width=4)
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=40, method=6)
        return buf.getvalue(), {"provider": "local_flat_pil", "note": "programmatic flat icon"}

    return timed(run)


def loremflickr(op):
    tags = ",".join(QUERY.split()[:3])
    url = f"https://loremflickr.com/640/480/{urllib.parse.quote(tags)}?lock=42"

    def run():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with op.open(req, timeout=40) as resp:
            return resp.read(), {"provider": "loremflickr", "status": resp.status}

    return timed(run)


def unsplash_source(op):
    # Legacy source.unsplash.com — often blocked for bulk; measure once.
    url = "https://source.unsplash.com/640x480/?" + urllib.parse.quote(QUERY)

    def run():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with op.open(req, timeout=40) as resp:
            return resp.read(), {"provider": "unsplash_source", "final": resp.geturl(), "status": resp.status}

    return timed(run)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    op = opener()
    results = []

    print(f"proxy={PROXY} query={QUERY!r}")
    print("--- single-shot probes ---")

    probes = [
        ("local_flat_pil", lambda: local_flat_svg_raster()),
        ("wikimedia", lambda: wikimedia(op)),
        ("openverse", lambda: openverse(op)),
        ("loremflickr", lambda: loremflickr(op)),
        ("unsplash_source", lambda: unsplash_source(op)),
        ("pollinations", lambda: pollinations(op, 0)),
        ("hf_inference", lambda: huggingface_inference(op)),
        ("together_no_key", lambda: together_try(op)),
    ]

    for name, fn in probes:
        print(f"\n[{name}] ...")
        meta, data = fn()
        meta["name"] = name
        path = save(f"{name}.bin", data)
        # try decode as image for sanity
        if data:
            try:
                im = Image.open(io.BytesIO(data))
                meta["image_size"] = list(im.size)
                meta["image_format"] = im.format
                # also write a preview
                preview = OUT_DIR / f"{name}.preview.jpg"
                im.convert("RGB").save(preview, quality=85)
                meta["preview"] = str(preview)
            except Exception as e:
                meta["decode_err"] = str(e)
        if path:
            meta["saved"] = path
        results.append(meta)
        print(json.dumps({k: meta[k] for k in meta if k != "image_url"}, ensure_ascii=False))

    # Pollinations rate-limit probe: 3 quick requests
    print("\n--- pollinations burst (3) ---")
    burst = []
    for i in range(3):
        meta, data = pollinations(op, attempt=i + 1)
        meta["name"] = f"pollinations_burst_{i+1}"
        burst.append(meta)
        print(i + 1, meta.get("ok"), meta.get("ms"), meta.get("error"))
        time.sleep(1)

    # Estimate for 5000
    estimates = []
    for r in results:
        name = r["name"]
        if not r.get("ok"):
            estimates.append(
                {
                    "name": name,
                    "feasible_5000": False,
                    "reason": r.get("error") or "request failed",
                }
            )
            continue
        ms = max(r["ms"], 1)
        # naive sequential estimate
        hours = (5000 * ms / 1000) / 3600
        notes = ""
        if name == "pollinations":
            # known free limit ~45s/image
            hours = (5000 * 48) / 3600
            notes = "anonymous free tier ~1 img / 45s (402 if faster)"
            feasible = False
        elif name.startswith("local_"):
            feasible = True
            notes = "unlimited local CPU; style is template/programmatic"
        elif name in {"wikimedia", "openverse", "loremflickr"}:
            # add polite delay assumption 0.5–1.5s
            hours = (5000 * (ms / 1000 + 0.8)) / 3600
            feasible = True
            notes = "search+download; subject to API etiquette / occasional 403"
        elif name == "unsplash_source":
            feasible = False
            notes = "policy forbids bulk local download"
        else:
            feasible = False
            notes = "needs paid/key for volume"
        estimates.append(
            {
                "name": name,
                "per_image_ms_observed": r["ms"],
                "est_hours_5000_seq": round(hours, 1),
                "feasible_5000_free_fast": feasible and hours <= 12,
                "notes": notes,
            }
        )

    report = {
        "query": QUERY,
        "proxy": PROXY,
        "probes": results,
        "pollinations_burst": burst,
        "estimates_5000": estimates,
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== estimate ===")
    for e in estimates:
        print(json.dumps(e, ensure_ascii=False))
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
