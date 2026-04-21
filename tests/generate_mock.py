"""Generate mock viloyat data for benchmarking archive formats.

Creates structure:
  MOCK_ROOT/
    Buxoro/Unprocessed/2A/<files>
    Jizzax/Unprocessed/2A/<files>
    ...
File contents simulate real data: mostly random bytes (incompressible, like PDF/JPG)
with some compressible text mixed in.
"""
import os
import sys
import random
import argparse
from pathlib import Path

VILOYATS = ["Buxoro", "Jizzax", "Qoraqalpoq", "Samarqand", "Toshkent"]


def gen_file(path: Path, size_bytes: int, compressible_ratio: float = 0.1):
    """Write a file of target size. compressible_ratio in [0,1] = share of
    repeating pattern (compressible); rest is random bytes."""
    CHUNK = 1 << 20  # 1MB
    comp_chunk = (b"KOSMIK-ARCHIVE-TEST-DATA-" * 64)[:CHUNK]
    remaining = size_bytes
    with open(path, "wb", buffering=CHUNK) as f:
        while remaining > 0:
            n = min(CHUNK, remaining)
            if random.random() < compressible_ratio:
                f.write(comp_chunk[:n])
            else:
                f.write(os.urandom(n))
            remaining -= n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"d:\2A-Unprocessed\mock", help="Root folder")
    ap.add_argument("--viloyats", type=int, default=3, help="Number of viloyats")
    ap.add_argument("--files-per-viloyat", type=int, default=20)
    ap.add_argument("--file-size-mb", type=float, default=5.0, help="Avg file size in MB")
    ap.add_argument("--compressible", type=float, default=0.1,
                    help="Fraction of compressible content (0..1)")
    args = ap.parse_args()

    root = Path(args.root)
    if root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    total_files = 0
    for i in range(args.viloyats):
        name = VILOYATS[i % len(VILOYATS)]
        if i >= len(VILOYATS):
            name = f"{name}_{i}"
        v2a = root / name / "Unprocessed" / "2A"
        v2a.mkdir(parents=True, exist_ok=True)
        # Also create Processed with some files to verify they're skipped
        vproc = root / name / "Processed" / "2A"
        vproc.mkdir(parents=True, exist_ok=True)
        gen_file(vproc / "SHOULD_NOT_BE_INCLUDED.bin", 1024, 0)

        for j in range(args.files_per_viloyat):
            # Vary file size +/- 50%
            size = int(args.file_size_mb * 1024 * 1024 * random.uniform(0.5, 1.5))
            ext = random.choice([".pdf", ".jpg", ".docx", ".xlsx"])
            fpath = v2a / f"file_{j:03d}{ext}"
            gen_file(fpath, size, args.compressible)
            total_bytes += size
            total_files += 1
        print(f"  {name}: {args.files_per_viloyat} files")

    print(f"\nGenerated: {total_files} files, {total_bytes / (1024*1024):.1f} MB total")
    print(f"Root: {root}")


if __name__ == "__main__":
    main()
