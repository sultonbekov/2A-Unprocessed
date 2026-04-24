#!/usr/bin/env python3

import sys
import os
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

import py7zr
from py7zr import FILTER_COPY

IO_BUFFER_SIZE = 8 * 1024 * 1024
UNPROCESSED_DIR = "Unprocessed"
TARGET_DIR = "2A"
ARCHIVE_NAME = "2A.7z"
PROGRESS_UPDATE_BYTES = 128 * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

FAST_FILTERS = [{"id": FILTER_COPY}]


def format_size(n: float) -> str:
    size = float(n)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def calculate_folder_size(path: str) -> int:
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += calculate_folder_size(entry.path)
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return total


def find_viloyats(root: Path) -> list:
    viloyats = []
    if not root.exists() or not root.is_dir():
        return viloyats
    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue
        target = item / UNPROCESSED_DIR / TARGET_DIR
        if target.exists() and target.is_dir():
            viloyats.append({
                "name": item.name,
                "path": str(item),
                "target_path": str(target),
            })
    return viloyats


def list_files(target: Path) -> list:
    target_str = str(target)
    prefix_len = len(target_str) + 1
    entries = []
    for root, _dirs, files in os.walk(target_str):
        for fn in files:
            full = os.path.join(root, fn)
            arc = full[prefix_len:]
            entries.append((full, arc))
    return entries


def archive_single_viloyat(viloyat: dict, output_root: Path) -> dict:
    name = viloyat["name"]
    target = Path(viloyat["target_path"])

    viloyat_out = output_root / name
    viloyat_out.mkdir(parents=True, exist_ok=True)
    archive_path = viloyat_out / ARCHIVE_NAME

    file_entries = list_files(target)

    files_done = 0
    bytes_done = 0

    logger.info(f"Arxivlanmoqda: {name} ({len(file_entries)} fayl)")

    with py7zr.SevenZipFile(archive_path, 'w', filters=FAST_FILTERS) as archive:
        for full_path, arc_name in file_entries:
            try:
                file_size = os.path.getsize(full_path)
                archive.write(full_path, arc_name)
                files_done += 1
                bytes_done += file_size
            except Exception as e:
                logger.warning(f"O'tkazib yuborildi {full_path}: {e}")

    archive_size = os.path.getsize(archive_path)
    logger.info(f"✓ {name}: {files_done} fayl, {format_size(archive_size)}")

    return {
        "viloyat_name": name,
        "archive_path": str(archive_path),
        "files_archived": files_done,
        "original_size": bytes_done,
        "archive_size": archive_size,
    }


def main():
    if len(sys.argv) != 3:
        print("\n" + "=" * 70)
        print("  KOSMIK Arxivlash - Lokal versiya (7z, parallel)")
        print("=" * 70)
        print("\n  Ishlatish:")
        print('    python archive.py "INPUT_PAPKA" "OUTPUT_PAPKA"')
        print("\n  Misol:")
        print('    python archive.py "D:\\Data\\Input" "D:\\Data\\Output"')
        print("\n  INPUT:  Viloyatlar joylashgan papka")
        print("  OUTPUT: Arxivlar saqlanadigan papka")
        print("=" * 70 + "\n")
        sys.exit(1)

    input_path = Path(sys.argv[1])   # INPUT: Viloyatlar joylashgan papka
    output_path = Path(sys.argv[2])  # OUTPUT: Arxivlar saqlanadigan papka

    print("\n" + "=" * 70)
    print("  KOSMIK Arxivlash")
    print("=" * 70)
    print(f"  INPUT:  {input_path}")
    print(f"  OUTPUT: {output_path}")
    print("=" * 70 + "\n")

    if not input_path.exists() or not input_path.is_dir():
        logger.error(f"INPUT papka topilmadi: {input_path}")
        sys.exit(1)

    viloyats = find_viloyats(input_path)
    if not viloyats:
        logger.error("Viloyatlar topilmadi (Unprocessed/2A strukturasi yo'q)")
        sys.exit(1)

    logger.info(f"Topildi: {len(viloyats)} viloyat")
    for v in viloyats:
        logger.info(f"  - {v['name']}")

    output_path.mkdir(parents=True, exist_ok=True)

    start = datetime.now()
    cpu_count = os.cpu_count() or 4
    max_workers = min(len(viloyats), cpu_count)
    results = []

    logger.info(f"\nBoshlandi: {max_workers} parallel thread\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(archive_single_viloyat, v, output_path): v
            for v in viloyats
        }
        for fut in as_completed(futures):
            v = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                logger.error(f"Xatolik {v['name']}: {e}")

    elapsed = (datetime.now() - start).total_seconds()
    total_files = sum(r["files_archived"] for r in results)
    total_original = sum(r["original_size"] for r in results)
    total_archive = sum(r["archive_size"] for r in results)
    speed = (total_original / (1024 * 1024)) / elapsed if elapsed > 0 else 0

    print("\n" + "=" * 70)
    print("  NATIJA")
    print("=" * 70)
    print(f"  Viloyatlar:      {len(results)}")
    print(f"  Fayllar:         {total_files}")
    print(f"  Asl hajm:        {format_size(total_original)}")
    print(f"  Arxiv hajm:      {format_size(total_archive)}")
    print(f"  Vaqt:            {elapsed:.2f}s")
    print(f"  Tezlik:          {speed:.1f} MB/s")
    print(f"  Saqlandi:        {output_path}")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
