"""After B2 examples finish, re-apply missing4 image patch and repack."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
WORK = ROOT / "_b2_pack_work"
PACK = ROOT / "packs" / "demo_b2.deword"
PY = sys.executable


def examples_running() -> bool:
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                "Where-Object { $_.CommandLine -match 'fill_level_examples_zh' }).Count",
            ],
            text=True,
            timeout=30,
        )
        return int((out or "0").strip() or "0") > 0
    except Exception as e:
        print("check err", e, flush=True)
        return False


def main() -> None:
    subprocess.check_call([PY, "-u", str(ROOT / "tools" / "_reapply_b2_missing4_patch.py")])
    print("waiting for examples to finish…", flush=True)
    while examples_running():
        time.sleep(30)
        print("  still running examples…", flush=True)
    print("examples done — reapply patch", flush=True)
    subprocess.check_call([PY, "-u", str(ROOT / "tools" / "_reapply_b2_missing4_patch.py")])
    words = json.loads((WORK / "words.json").read_text(encoding="utf-8"))
    ready = sum(1 for w in words if (w.get("image") or {}).get("status") == "ready")
    print(f"ready={ready}/{len(words)}", flush=True)
    manifest = json.loads((WORK / "manifest.json").read_text(encoding="utf-8"))
    manifest["image_status"] = "filled" if ready == len(words) else f"partial:{ready}/{len(words)}"
    manifest["content_hash"] = hashlib.sha256((WORK / "words.json").read_bytes()).hexdigest()[:16]
    (WORK / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("repacking…", flush=True)
    if PACK.exists():
        PACK.unlink()
    files = [p for p in WORK.rglob("*") if p.is_file() and p.name != "_missing4_image_patch.json"]
    with zipfile.ZipFile(PACK, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, p in enumerate(files, 1):
            zf.write(p, p.relative_to(WORK).as_posix())
            if i % 1000 == 0:
                print(f"  zip {i}/{len(files)}", flush=True)
    print(f"pack {PACK} {PACK.stat().st_size/1024/1024:.2f}MB", flush=True)


if __name__ == "__main__":
    main()
