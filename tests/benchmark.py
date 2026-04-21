"""Benchmark all 3 archive formats via the HTTP API."""
import time
import json
import shutil
import urllib.request
from pathlib import Path

API = "http://localhost:5000/api"
INPUT = r"d:\2A-Unprocessed\mock"
OUTPUT_BASE = r"d:\2A-Unprocessed\mock_out"


def http_post(path, body):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def http_get(path):
    with urllib.request.urlopen(f"{API}{path}", timeout=60) as r:
        return json.loads(r.read())


def run_one(fmt, quality):
    out = Path(OUTPUT_BASE) / f"{fmt}_{quality}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    resp = http_post("/archive", {
        "input_path": INPUT,
        "output_path": str(out),
        "format": fmt,
        "quality": quality,
    })
    if not resp.get("success"):
        return {"fmt": fmt, "quality": quality, "error": resp.get("error")}
    job_id = resp["job_id"]

    while True:
        time.sleep(0.5)
        status = http_get(f"/progress/{job_id}")
        st = status.get("status")
        if st == "completed":
            elapsed = time.time() - t0
            return {
                "fmt": fmt,
                "quality": quality,
                "elapsed": elapsed,
                "orig": status.get("original_size"),
                "archive": status.get("archive_size"),
                "speed": status.get("speed"),
                "files": status.get("files_archived"),
            }
        if st == "error":
            return {"fmt": fmt, "quality": quality, "error": status.get("error")}


def main():
    # Check available formats
    formats = http_get("/formats")["formats"]
    print("Available formats:", [(f["id"], f["available"]) for f in formats])
    print()

    cases = [
        ("zip", "fast"),
        ("zip", "best"),
        ("7z", "fast"),
        ("7z", "balanced"),
        ("rar", "fast"),
        ("rar", "balanced"),
    ]

    print(f"{'FORMAT':<12} {'QUALITY':<10} {'TIME':>8} {'ORIG':>12} {'ARCHIVE':>12} {'RATIO':>8} {'SPEED':>12}")
    print("-" * 80)
    for fmt, quality in cases:
        fobj = next((f for f in formats if f["id"] == fmt), None)
        if not fobj or not fobj["available"]:
            print(f"{fmt:<12} {quality:<10} SKIPPED (not available)")
            continue
        r = run_one(fmt, quality)
        if "error" in r:
            print(f"{fmt:<12} {quality:<10} ERROR: {r['error']}")
        else:
            print(f"{fmt:<12} {quality:<10} {r['elapsed']:>7.2f}s {r['orig']:>12} {r['archive']:>12} "
                  f"{'—':>8} {r['speed']:>12}")


if __name__ == "__main__":
    main()
