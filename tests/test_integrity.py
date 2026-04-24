"""
KOSMIK Arxivlash - Ma'lumotlar butunligi testi

Bu test 20 marta arxivlash jarayonini bajaradi va har safar tekshiradi:
  1. Manba fayllar o'zgarmaganmi? (SHA-256 hash taqqoslash)
  2. Hech qanday manba fayl o'chirilmadimi?
  3. Yangi arxiv hamma fayllarni o'z ichiga olyaptimi?

Agar BIRORTA test muvaffaqiyatsiz bo'lsa - demak kod xavfli,
manba ma'lumotlariga teginyapti. Bu QAT'IYAN mumkin emas.
"""

import hashlib
import os
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Backend modullarini import qilish uchun yo'l qo'shamiz
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import py7zr  # noqa: E402
from archiver import run_archive_job, find_viloyats  # noqa: E402
import jobs  # noqa: E402


# =====================================================================
# Test uchun mock ma'lumotlar yaratish
# =====================================================================

def _write_random_file(path: Path, size: int, seed: int) -> None:
    """Aniqlangan seed bilan tasodifiy mazmunli fayl yaratadi"""
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(bytes(rng.getrandbits(8) for _ in range(size)))


def create_mock_structure(root: Path, viloyat_names: list,
                          files_per_viloyat: int, seed_base: int) -> dict:
    """
    Test uchun Viloyat/Unprocessed/2A strukturasini yaratadi.

    Natija: fayllarning SHA-256 hashlari ro'yxati (keyin tekshirish uchun)
    """
    hashes = {}
    for i, vname in enumerate(viloyat_names):
        target = root / vname / "Unprocessed" / "2A"
        target.mkdir(parents=True, exist_ok=True)

        for j in range(files_per_viloyat):
            # Har xil hajmdagi fayllar: 1 KB dan 50 KB gacha
            size = 1024 + ((i * 7 + j * 13) % 50) * 1024
            subdir = "docs" if j % 2 == 0 else "scans"
            file_path = target / subdir / f"file_{j:03d}.bin"
            _write_random_file(file_path, size, seed_base + i * 1000 + j)
            hashes[str(file_path)] = _sha256(file_path)
    return hashes


def _sha256(path: Path) -> str:
    """Faylning SHA-256 hashini qaytaradi"""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def snapshot_source(root: Path) -> dict:
    """
    Manba papkadagi hamma fayllarning (yo'l, hajm, hash, mtime) holatini oladi.
    Arxivlashdan oldin va keyin taqqoslash uchun.
    """
    snap = {}
    for p in root.rglob('*'):
        if p.is_file():
            st = p.stat()
            snap[str(p)] = {
                'size': st.st_size,
                'mtime': st.st_mtime,
                'hash': _sha256(p),
            }
    return snap


# =====================================================================
# Arxivlash va tekshirish
# =====================================================================

def run_archive_sync(input_dir: Path, output_dir: Path) -> dict:
    """Arxivlashni sinxron (kutib) ishga tushiradi"""
    job_id = f"test_{int(time.time() * 1000000)}"
    jobs.create_job(job_id)
    # Thread ishlatmasdan to'g'ridan-to'g'ri chaqiramiz
    run_archive_job(job_id, str(input_dir), str(output_dir))
    return jobs.get_job(job_id)


def verify_archive_contents(archive_path: Path, expected_files: set) -> tuple:
    """
    Arxivni vaqtinchalik papkaga ochadi va ichidagi fayllarni tekshiradi.

    Natija: (muvaffaqiyat, xato_xabari)
    """
    if not archive_path.exists():
        return False, f"Arxiv topilmadi: {archive_path}"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        try:
            with py7zr.SevenZipFile(archive_path, 'r') as a:
                a.extractall(path=tmp)
        except Exception as e:
            return False, f"Arxivni ochib bo'lmadi: {e}"

        found = set()
        for f in tmp_p.rglob('*'):
            if f.is_file():
                rel = f.relative_to(tmp_p).as_posix()
                found.add(rel)

        missing = expected_files - found
        extra = found - expected_files
        if missing:
            return False, f"Arxivda {len(missing)} fayl yo'q: {list(missing)[:3]}"
        if extra:
            return False, f"Arxivda {len(extra)} ortiqcha fayl: {list(extra)[:3]}"
    return True, ""


def run_one_iteration(iteration: int) -> tuple:
    """
    Bitta test iteratsiyasi.
    Natija: (muvaffaqiyat: bool, xabar: str, davomiylik_sek: float)
    """
    start = time.time()
    with tempfile.TemporaryDirectory(prefix=f"kosmik_test_{iteration}_") as tmp:
        tmp_root = Path(tmp)
        input_dir = tmp_root / "input"
        output_dir = tmp_root / "output"
        input_dir.mkdir()

        # Mock ma'lumot yaratamiz - har safar boshqa seed
        seed = 42000 + iteration * 111
        viloyat_names = ["Andijon", "Buxoro", "Fargona"]
        files_per_v = 8
        create_mock_structure(input_dir, viloyat_names, files_per_v, seed)

        # Arxivlashdan OLDIN manba holatini oladik
        before = snapshot_source(input_dir)
        if not before:
            return False, "Manba fayllar yaratilmadi", time.time() - start

        # Arxivlash
        job = run_archive_sync(input_dir, output_dir)
        if job.get("status") != "completed":
            return False, f"Arxivlash bajarilmadi: {job.get('error') or job.get('status')}", time.time() - start

        # Arxivlashdan KEYIN manba holatini oladik
        after = snapshot_source(input_dir)

        # ========== 1-TEKSHIRUV: manba fayllar o'zgarmaganmi? ==========
        if set(before.keys()) != set(after.keys()):
            missing = set(before) - set(after)
            added = set(after) - set(before)
            return False, f"Manba fayllar ro'yxati o'zgardi! yo'q: {missing}, qo'shildi: {added}", time.time() - start

        for path, meta_before in before.items():
            meta_after = after[path]
            if meta_before['hash'] != meta_after['hash']:
                return False, f"FAYL MAZMUNI O'ZGARDI: {path}", time.time() - start
            if meta_before['size'] != meta_after['size']:
                return False, f"FAYL HAJMI O'ZGARDI: {path}", time.time() - start

        # ========== 2-TEKSHIRUV: arxiv to'g'ri yaratildimi? ==========
        for vname in viloyat_names:
            archive_path = output_dir / vname / "2A.7z"
            target_dir = input_dir / vname / "Unprocessed" / "2A"
            expected = set(
                f.relative_to(target_dir).as_posix()
                for f in target_dir.rglob('*') if f.is_file()
            )
            ok, msg = verify_archive_contents(archive_path, expected)
            if not ok:
                return False, f"[{vname}] {msg}", time.time() - start

    return True, "OK", time.time() - start


# =====================================================================
# Asosiy test siklli
# =====================================================================

def main():
    ITERATIONS = 20
    print("=" * 70)
    print(f"  KOSMIK Arxivlash - Butunlik testi ({ITERATIONS} iteratsiya)")
    print("=" * 70)
    print()

    passed = 0
    failed = 0
    total_time = 0.0
    failures = []

    for i in range(1, ITERATIONS + 1):
        ok, msg, dur = run_one_iteration(i)
        total_time += dur
        status = "PASS" if ok else "FAIL"
        marker = "+" if ok else "X"
        print(f"  [{marker}] Iteratsiya {i:2d}/{ITERATIONS}: {status} ({dur:.2f}s) - {msg}")
        if ok:
            passed += 1
        else:
            failed += 1
            failures.append((i, msg))

    print()
    print("=" * 70)
    print(f"  Natija: {passed}/{ITERATIONS} muvaffaqiyatli, {failed} xato")
    print(f"  Umumiy vaqt: {total_time:.2f}s "
          f"(o'rtacha {total_time / ITERATIONS:.2f}s / iteratsiya)")
    print("=" * 70)

    if failures:
        print("\nXatolar:")
        for i, msg in failures:
            print(f"  Iteratsiya {i}: {msg}")
        sys.exit(1)

    print("\nHAMMA TESTLAR MUVAFFAQIYATLI! Manba ma'lumotlar xavfsiz.")
    sys.exit(0)


if __name__ == '__main__':
    main()
