# Manba fayllar faqat o'qiladi (input papka) - hech qachon o'zgartirilmaydi!

import os
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import py7zr
from py7zr import FILTER_COPY

from config import (
    UNPROCESSED_DIR, TARGET_DIR, ARCHIVE_NAME,
    PROGRESS_UPDATE_BYTES,
)
import jobs

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


def calculate_total_size(viloyats: list) -> int:
    if not viloyats:
        return 0
    total = 0
    with ThreadPoolExecutor(max_workers=min(len(viloyats), 16)) as ex:
        for size in ex.map(lambda v: calculate_folder_size(v["target_path"]), viloyats):
            total += size
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


def archive_single_viloyat(viloyat: dict, output_root: Path, job_id: str) -> dict:
    name = viloyat["name"]
    target = Path(viloyat["target_path"])

    viloyat_out = output_root / name
    viloyat_out.mkdir(parents=True, exist_ok=True)
    archive_path = viloyat_out / ARCHIVE_NAME

    file_entries = list_files(target)

    files_done = 0
    bytes_done = 0
    bytes_buf = 0
    files_buf = 0

    with py7zr.SevenZipFile(archive_path, 'w', filters=FAST_FILTERS) as archive:
        for full_path, arc_name in file_entries:
            try:
                file_size = os.path.getsize(full_path)
                archive.write(full_path, arc_name)
                files_done += 1
                bytes_done += file_size
                bytes_buf += file_size
                files_buf += 1
                if bytes_buf >= PROGRESS_UPDATE_BYTES:
                    jobs.tick_progress(job_id, name, bytes_buf, files_buf)
                    bytes_buf = 0
                    files_buf = 0
            except Exception as e:
                logger.warning(f"Fayl o'tkazib yuborildi {full_path}: {e}")

    if bytes_buf or files_buf:
        jobs.tick_progress(job_id, name, bytes_buf, files_buf)

    archive_size = os.path.getsize(archive_path)
    jobs.mark_viloyat_done(job_id)
    logger.info(f"Tayyor: {archive_path} ({files_done} fayl, "
                f"{format_size(archive_size)})")

    return {
        "viloyat_name": name,
        "archive_path": str(archive_path),
        "files_archived": files_done,
        "original_size": bytes_done,
        "archive_size": archive_size,
    }


def run_archive_job(job_id: str, input_path: str, output_path: str) -> None:
    try:
        start = datetime.now()
        input_p = Path(input_path)
        output_p = Path(output_path)

        if not input_p.exists() or not input_p.is_dir():
            jobs.update_job(job_id, status="error",
                            error="Kirish papka topilmadi")
            return

        viloyats = find_viloyats(input_p)
        if not viloyats:
            jobs.update_job(
                job_id, status="error",
                error="Viloyatlar topilmadi (Unprocessed/2A strukturasi yo'q)",
            )
            return

        output_p.mkdir(parents=True, exist_ok=True)

        jobs.update_job(job_id, status="calculating")
        total_size = calculate_total_size(viloyats)

        jobs.update_job(
            job_id,
            status="archiving",
            total_bytes=total_size,
            total_viloyats=len(viloyats),
            processed_bytes=0,
            processed_files=0,
            completed_viloyats=0,
            start_time=start.isoformat(),
        )

        cpu_count = os.cpu_count() or 4
        max_workers = min(len(viloyats), cpu_count)
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(archive_single_viloyat, v, output_p, job_id): v
                for v in viloyats
            }
            for fut in as_completed(futures):
                v = futures[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    logger.error(f"Viloyat arxivlash xatosi {v['name']}: {e}")

        elapsed = (datetime.now() - start).total_seconds()
        total_files = sum(r["files_archived"] for r in results)
        total_original = sum(r["original_size"] for r in results)
        total_archive = sum(r["archive_size"] for r in results)
        speed = (total_original / (1024 * 1024)) / elapsed if elapsed > 0 else 0

        jobs.update_job(
            job_id,
            status="completed",
            viloyat_count=len(results),
            viloyats=results,
            files_archived=total_files,
            original_size=format_size(total_original),
            archive_size=format_size(total_archive),
            elapsed_seconds=f"{elapsed:.2f}",
            speed=f"{speed:.1f} MB/s",
            output_path=str(output_p),
            processed_bytes=total_original,
            processed_files=total_files,
            completed_viloyats=len(results),
        )
        logger.info(f"Ish tayyor {job_id}: {elapsed:.2f}s, "
                    f"{total_files} fayl, {speed:.1f} MB/s")

    except Exception as e:
        logger.exception(f"Arxivlash xatosi: {e}")
        jobs.update_job(job_id, status="error", error=str(e))
