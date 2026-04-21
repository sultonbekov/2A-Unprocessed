"""
Viloyat Archiver - Professional ZIP Archive Tool
Backend API for archiving 2A folders from Viloyat/Unprocessed structure
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import os
import zipfile
import shutil
import tempfile
import webbrowser
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid
import subprocess
import logging

# Ultra-fast IO buffer size (8MB) - 512x bigger than default 16KB
IO_BUFFER_SIZE = 8 * 1024 * 1024

# Optional 7z support
try:
    import py7zr
    from py7zr import FILTER_LZMA2, FILTER_COPY, PRESET_DEFAULT
    HAS_7Z = True
except ImportError:
    HAS_7Z = False

# Optional RAR support - detect Rar.exe
def _find_rar_exe():
    candidates = [
        r"C:\Program Files\WinRAR\Rar.exe",
        r"C:\Program Files (x86)\WinRAR\Rar.exe",
        shutil.which("rar"),
        shutil.which("Rar.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None

RAR_EXE = _find_rar_exe()
HAS_RAR = RAR_EXE is not None

# Supported archive formats
ARCHIVE_FORMATS = {
    "zip": {"ext": "zip", "available": True, "name": "ZIP (быстро, без сжатия)"},
    "7z": {"ext": "7z", "available": HAS_7Z, "name": "7-Zip (максимальное качество)"},
    "rar": {"ext": "rar", "available": HAS_RAR, "name": "RAR (WinRAR)"},
}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the frontend directory path
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / 'frontend'

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='')
CORS(app)


# In-memory job registry for progress tracking
JOBS = {}
JOBS_LOCK = threading.Lock()


class ViloyatArchiver:
    """Professional archiver for Viloyat folder structures - optimized for TB-scale data"""
    
    def __init__(self):
        self.supported_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.png', '.txt']
    
    def validate_input_path(self, input_path: str, count_files: bool = False) -> dict:
        """Validate the input folder structure - finds all Viloyat folders.
        count_files=False avoids slow recursive scan for TB-scale data.
        """
        path = Path(input_path)
        
        if not path.exists():
            return {"valid": False, "error": "Путь не существует"}
        
        if not path.is_dir():
            return {"valid": False, "error": "Путь не является папкой"}
        
        viloyats = []
        total_files = 0
        
        for item in path.iterdir():
            if item.is_dir():
                unprocessed_path = item / "Unprocessed"
                folder_2a = unprocessed_path / "2A"
                
                if unprocessed_path.exists() and folder_2a.exists():
                    file_count = self._count_files(folder_2a) if count_files else 0
                    viloyats.append({
                        "name": item.name,
                        "path": str(item),
                        "folder_2a_path": str(folder_2a),
                        "file_count": file_count
                    })
                    total_files += file_count
        
        if not viloyats:
            return {"valid": False, "error": "Вилоятлар топилмади (Unprocessed/2A структураси йўқ)"}
        
        return {
            "valid": True,
            "viloyat_count": len(viloyats),
            "viloyats": viloyats,
            "total_files": total_files
        }
    
    def _count_files(self, folder_path: Path) -> int:
        """Count all files in a folder recursively (fast using os.scandir)"""
        count = 0
        try:
            for entry in os.scandir(folder_path):
                if entry.is_file(follow_symlinks=False):
                    count += 1
                elif entry.is_dir(follow_symlinks=False):
                    count += self._count_files(entry.path)
        except (PermissionError, OSError):
            pass
        return count
    
    # ---- Progress helpers ----
    def _tick_progress(self, job_id, viloyat_name, bytes_delta, files_delta):
        if not job_id:
            return
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["processed_bytes"] = JOBS[job_id].get("processed_bytes", 0) + bytes_delta
                JOBS[job_id]["processed_files"] = JOBS[job_id].get("processed_files", 0) + files_delta
                JOBS[job_id]["current_viloyat"] = viloyat_name
    
    def _mark_viloyat_done(self, job_id):
        if not job_id:
            return
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["completed_viloyats"] = JOBS[job_id].get("completed_viloyats", 0) + 1
    
    # ---- Format dispatcher ----
    def _archive_single_viloyat(self, viloyat: dict, output_path: Path, job_id: str = None,
                                 fmt: str = "zip", quality: str = "fast") -> dict:
        """Archive a single viloyat in selected format"""
        viloyat_name = viloyat["name"]
        folder_2a = Path(viloyat["folder_2a_path"])
        viloyat_output = output_path / viloyat_name
        viloyat_output.mkdir(parents=True, exist_ok=True)
        
        if fmt == "7z":
            if not HAS_7Z:
                raise RuntimeError("7z не установлен (pip install py7zr)")
            return self._archive_7z(viloyat_name, folder_2a, viloyat_output, job_id, quality)
        elif fmt == "rar":
            if not HAS_RAR:
                raise RuntimeError("RAR не найден (установите WinRAR)")
            return self._archive_rar(viloyat_name, folder_2a, viloyat_output, job_id, quality)
        else:
            return self._archive_zip(viloyat_name, folder_2a, viloyat_output, job_id, quality)
    
    # ---- ZIP (ultra fast, no compression) ----
    def _archive_zip(self, viloyat_name, folder_2a: Path, viloyat_output: Path,
                     job_id: str, quality: str) -> dict:
        folder_2a_str = str(folder_2a)
        folder_2a_len = len(folder_2a_str) + 1
        zip_filename = viloyat_output / "2A.zip"
        
        # quality: fast = STORED; best = DEFLATED level 6
        if quality == "best":
            compress_type = zipfile.ZIP_DEFLATED
            compresslevel = 6
        else:
            compress_type = zipfile.ZIP_STORED
            compresslevel = None
        
        files_archived = 0
        original_size = 0
        bytes_buf = 0
        files_buf = 0
        UPDATE_THRESHOLD = 256 * 1024 * 1024
        
        with open(zip_filename, 'wb', buffering=IO_BUFFER_SIZE) as fp:
            with zipfile.ZipFile(fp, 'w', compress_type, allowZip64=True, compresslevel=compresslevel) as zipf:
                for root, dirs, files in os.walk(folder_2a_str):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        arcname = file_path[folder_2a_len:]
                        try:
                            file_size = os.path.getsize(file_path)
                            zinfo = zipfile.ZipInfo.from_file(file_path, arcname)
                            zinfo.compress_type = compress_type
                            with open(file_path, 'rb', buffering=IO_BUFFER_SIZE) as src:
                                with zipf.open(zinfo, 'w', force_zip64=True) as dst:
                                    shutil.copyfileobj(src, dst, IO_BUFFER_SIZE)
                            files_archived += 1
                            original_size += file_size
                            bytes_buf += file_size
                            files_buf += 1
                            if bytes_buf >= UPDATE_THRESHOLD:
                                self._tick_progress(job_id, viloyat_name, bytes_buf, files_buf)
                                bytes_buf = 0
                                files_buf = 0
                        except Exception as e:
                            logger.warning(f"Skipped {file_path}: {e}")
        
        if bytes_buf or files_buf:
            self._tick_progress(job_id, viloyat_name, bytes_buf, files_buf)
        
        archive_size = os.path.getsize(zip_filename)
        self._mark_viloyat_done(job_id)
        logger.info(f"ZIP: {zip_filename} ({files_archived} files, {self._format_size(archive_size)})")
        
        return {
            "viloyat_name": viloyat_name,
            "archive_path": str(zip_filename),
            "files_archived": files_archived,
            "original_size": original_size,
            "archive_size": archive_size,
        }
    
    # ---- 7z (high quality) ----
    def _archive_7z(self, viloyat_name, folder_2a: Path, viloyat_output: Path,
                    job_id: str, quality: str) -> dict:
        archive_path = viloyat_output / "2A.7z"
        
        # Quality presets
        if quality == "best":
            filters = [{"id": py7zr.FILTER_LZMA2, "preset": 9}]
        elif quality == "balanced":
            filters = [{"id": py7zr.FILTER_LZMA2, "preset": 5}]
        else:  # fast
            filters = [{"id": py7zr.FILTER_LZMA2, "preset": 1}]
        
        # Enumerate files and compute totals first
        file_entries = []
        folder_2a_str = str(folder_2a)
        folder_2a_len = len(folder_2a_str) + 1
        for root, dirs, files in os.walk(folder_2a_str):
            for fn in files:
                fp = os.path.join(root, fn)
                file_entries.append((fp, fp[folder_2a_len:]))
        
        files_archived = 0
        original_size = 0
        bytes_buf = 0
        files_buf = 0
        UPDATE_THRESHOLD = 128 * 1024 * 1024
        
        with py7zr.SevenZipFile(archive_path, 'w', filters=filters) as archive:
            for fp, arc in file_entries:
                try:
                    fs = os.path.getsize(fp)
                    archive.write(fp, arc)
                    files_archived += 1
                    original_size += fs
                    bytes_buf += fs
                    files_buf += 1
                    if bytes_buf >= UPDATE_THRESHOLD:
                        self._tick_progress(job_id, viloyat_name, bytes_buf, files_buf)
                        bytes_buf = 0
                        files_buf = 0
                except Exception as e:
                    logger.warning(f"Skipped {fp}: {e}")
        
        if bytes_buf or files_buf:
            self._tick_progress(job_id, viloyat_name, bytes_buf, files_buf)
        
        archive_size = os.path.getsize(archive_path)
        self._mark_viloyat_done(job_id)
        logger.info(f"7z: {archive_path} ({files_archived} files, {self._format_size(archive_size)})")
        
        return {
            "viloyat_name": viloyat_name,
            "archive_path": str(archive_path),
            "files_archived": files_archived,
            "original_size": original_size,
            "archive_size": archive_size,
        }
    
    # ---- RAR (via WinRAR Rar.exe) ----
    def _archive_rar(self, viloyat_name, folder_2a: Path, viloyat_output: Path,
                     job_id: str, quality: str) -> dict:
        archive_path = viloyat_output / "2A.rar"
        
        # Count files + size upfront for progress tracking
        files_total = 0
        original_size = 0
        for root, dirs, files in os.walk(folder_2a):
            for fn in files:
                try:
                    original_size += os.path.getsize(os.path.join(root, fn))
                    files_total += 1
                except OSError:
                    pass
        
        # RAR quality levels: -m0 store, -m1 fastest, -m3 normal, -m5 best
        level_map = {"fast": "-m1", "balanced": "-m3", "best": "-m5"}
        level = level_map.get(quality, "-m3")
        
        # Background thread: poll archive file size for progress
        stop_evt = threading.Event()
        last_reported = [0]
        
        def progress_watcher():
            while not stop_evt.is_set():
                try:
                    if archive_path.exists():
                        cur_size = os.path.getsize(archive_path)
                        # Estimate: archive grows proportionally to input consumed
                        # For -m1..-m5, ratio depends; we use archive_size growth as proxy for bytes_buf
                        # Report growth since last report, capped at original_size
                        if cur_size > last_reported[0]:
                            # Estimate ratio: original/cur ≈ 1 for most compressed data (PDF/JPG)
                            # So bytes processed ≈ cur_size
                            delta = min(cur_size, original_size) - last_reported[0]
                            if delta > 0:
                                self._tick_progress(job_id, viloyat_name, delta, 0)
                                last_reported[0] = min(cur_size, original_size)
                except OSError:
                    pass
                stop_evt.wait(2.0)
        
        watcher = threading.Thread(target=progress_watcher, daemon=True)
        watcher.start()
        
        try:
            # rar a -r -ep1 -m3 <archive> <folder>\*
            cmd = [
                RAR_EXE, "a", "-r", "-ep1", "-idq", level,
                str(archive_path),
                os.path.join(str(folder_2a), "*"),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode not in (0, 1):  # 0=success, 1=warning
                raise RuntimeError(f"RAR failed (code {result.returncode}): {result.stderr[:500]}")
        finally:
            stop_evt.set()
            watcher.join(timeout=3)
        
        # Final progress: ensure we counted everything
        remaining = original_size - last_reported[0]
        if remaining > 0:
            self._tick_progress(job_id, viloyat_name, remaining, files_total)
        else:
            self._tick_progress(job_id, viloyat_name, 0, files_total)
        
        archive_size = os.path.getsize(archive_path) if archive_path.exists() else 0
        self._mark_viloyat_done(job_id)
        logger.info(f"RAR: {archive_path} ({files_total} files, {self._format_size(archive_size)})")
        
        return {
            "viloyat_name": viloyat_name,
            "archive_path": str(archive_path),
            "files_archived": files_total,
            "original_size": original_size,
            "archive_size": archive_size,
        }
    
    def _calculate_total_size(self, viloyats: list) -> int:
        """Fast parallel size calculation for progress tracking"""
        def get_folder_size(path):
            total = 0
            try:
                for entry in os.scandir(path):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            total += entry.stat().st_size
                        elif entry.is_dir(follow_symlinks=False):
                            total += get_folder_size(entry.path)
                    except (PermissionError, OSError):
                        pass
            except (PermissionError, OSError):
                pass
            return total
        
        total = 0
        with ThreadPoolExecutor(max_workers=min(len(viloyats), 16)) as ex:
            for size in ex.map(lambda v: get_folder_size(v["folder_2a_path"]), viloyats):
                total += size
        return total
    
    def run_archive_job(self, job_id: str, input_path: str, output_path: str,
                         fmt: str = "zip", quality: str = "fast"):
        """Background job: archive all viloyats with progress tracking"""
        try:
            start_time = datetime.now()
            input_path_p = Path(input_path)
            output_path_p = Path(output_path)
            
            validation = self.validate_input_path(str(input_path_p))
            if not validation["valid"]:
                with JOBS_LOCK:
                    JOBS[job_id].update({"status": "error", "error": validation["error"]})
                return
            
            viloyats = validation["viloyats"]
            
            # Calculate total size for progress %
            with JOBS_LOCK:
                JOBS[job_id]["status"] = "calculating"
            total_size = self._calculate_total_size(viloyats)
            
            with JOBS_LOCK:
                JOBS[job_id].update({
                    "status": "archiving",
                    "total_bytes": total_size,
                    "total_viloyats": len(viloyats),
                    "processed_bytes": 0,
                    "processed_files": 0,
                    "completed_viloyats": 0,
                    "format": fmt,
                    "quality": quality,
                    "start_time": start_time.isoformat()
                })
            
            results = []
            # For CPU-heavy formats (7z/rar-best) limit concurrency to CPU cores
            if fmt in ("7z", "rar") and quality != "fast":
                max_workers = min(len(viloyats), os.cpu_count() or 4)
            else:
                max_workers = min(len(viloyats), (os.cpu_count() or 4) * 2)
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._archive_single_viloyat, v, output_path_p, job_id, fmt, quality): v
                    for v in viloyats
                }
                for future in as_completed(futures):
                    try:
                        results.append(future.result())
                    except Exception as e:
                        viloyat = futures[future]
                        logger.error(f"Failed to archive {viloyat['name']}: {e}")
            
            total_files = sum(r["files_archived"] for r in results)
            total_original = sum(r["original_size"] for r in results)
            total_archive = sum(r["archive_size"] for r in results)
            elapsed = (datetime.now() - start_time).total_seconds()
            
            speed_mb_s = (total_original / (1024*1024)) / elapsed if elapsed > 0 else 0
            
            with JOBS_LOCK:
                JOBS[job_id].update({
                    "status": "completed",
                    "viloyat_count": len(results),
                    "viloyats": results,
                    "files_archived": total_files,
                    "original_size": self._format_size(total_original),
                    "archive_size": self._format_size(total_archive),
                    "elapsed_seconds": f"{elapsed:.2f}",
                    "speed": f"{speed_mb_s:.1f} MB/s",
                    "output_path": str(output_path_p),
                    "processed_bytes": total_original,
                    "processed_files": total_files,
                    "completed_viloyats": len(results)
                })
            logger.info(f"Job {job_id}: {elapsed:.2f}s, {total_files} files, {speed_mb_s:.1f} MB/s")
        except Exception as e:
            logger.error(f"Archive job failed: {e}")
            with JOBS_LOCK:
                JOBS[job_id].update({"status": "error", "error": str(e)})
    
    def _format_size(self, size_bytes: float) -> str:
        """Format bytes to human readable string (up to PB)"""
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"


# Initialize archiver
archiver = ViloyatArchiver()


@app.route('/')
def serve_frontend():
    """Serve the frontend application"""
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory(FRONTEND_DIR, path)


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "Viloyat Archiver"})


@app.route('/api/validate', methods=['POST'])
def validate_path():
    """Validate input folder structure"""
    data = request.get_json()
    input_path = data.get('input_path', '')
    
    if not input_path:
        return jsonify({"valid": False, "error": "Укажите входной путь"}), 400
    
    result = archiver.validate_input_path(input_path)
    return jsonify(result)


@app.route('/api/formats', methods=['GET'])
def list_formats():
    """Return available archive formats"""
    return jsonify({
        "formats": [
            {"id": k, "name": v["name"], "ext": v["ext"], "available": v["available"]}
            for k, v in ARCHIVE_FORMATS.items()
        ],
        "qualities": [
            {"id": "fast", "name": "Быстро"},
            {"id": "balanced", "name": "Баланс"},
            {"id": "best", "name": "Максимальное качество"},
        ],
    })


@app.route('/api/archive', methods=['POST'])
def create_archive():
    """Start background archive job and return job_id immediately"""
    data = request.get_json()
    input_path = data.get('input_path', '')
    output_path = data.get('output_path', '')
    fmt = (data.get('format') or 'zip').lower()
    quality = (data.get('quality') or 'fast').lower()
    
    if not input_path or not output_path:
        return jsonify({"success": False, "error": "Укажите входной и выходной пути"}), 400
    
    if fmt not in ARCHIVE_FORMATS:
        return jsonify({"success": False, "error": f"Неизвестный формат: {fmt}"}), 400
    if not ARCHIVE_FORMATS[fmt]["available"]:
        return jsonify({"success": False, "error": f"Формат {fmt} недоступен на этой системе"}), 400
    if quality not in ("fast", "balanced", "best"):
        quality = "fast"
    
    job_id = uuid.uuid4().hex
    with JOBS_LOCK:
        JOBS[job_id] = {"status": "queued", "job_id": job_id, "format": fmt, "quality": quality}
    
    thread = threading.Thread(
        target=archiver.run_archive_job,
        args=(job_id, input_path, output_path, fmt, quality),
        daemon=True
    )
    thread.start()
    
    return jsonify({"success": True, "job_id": job_id})


@app.route('/api/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    """Get current job progress"""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    
    data = dict(job)
    total = data.get("total_bytes", 0)
    processed = data.get("processed_bytes", 0)
    data["percent"] = (processed / total * 100) if total > 0 else 0
    
    # Calculate ETA
    if data.get("start_time") and processed > 0 and total > 0:
        start = datetime.fromisoformat(data["start_time"])
        elapsed = (datetime.now() - start).total_seconds()
        speed = processed / elapsed if elapsed > 0 else 0
        remaining = (total - processed) / speed if speed > 0 else 0
        data["eta_seconds"] = int(remaining)
        data["current_speed"] = f"{speed / (1024*1024):.1f} MB/s"
        data["elapsed"] = int(elapsed)
    
    return jsonify(data)


@app.route('/api/browse', methods=['POST'])
def browse_directory():
    """Browse directory contents"""
    data = request.get_json()
    path = data.get('path', '')
    show_only_unprocessed = data.get('show_only_unprocessed', False)
    
    if not path:
        # Return drives on Windows including network drives
        import string
        drives = []
        
        # Local drives
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append({"name": drive, "type": "drive"})
        
        # Network drives
        try:
            import win32api
            import win32file
            drives_info = win32api.GetLogicalDriveStrings()
            for drive in drives_info.split('\x00')[:-1]:
                if drive and win32file.GetDriveType(drive) == win32file.DRIVE_REMOTE:
                    drives.append({"name": drive, "type": "network"})
        except ImportError:
            # Fallback - add common network paths
            drives.append({"name": "\\\\", "type": "network"})
        
        return jsonify({"items": drives, "current_path": ""})
    
    try:
        path = Path(path)
        if not path.exists():
            return jsonify({"error": "Path does not exist"}), 400
        
        items = []
        for item in sorted(path.iterdir()):
            # If showing only Unprocessed folders, filter them
            if show_only_unprocessed:
                if item.is_dir() and item.name == "Unprocessed":
                    # Check if it contains 2A folder
                    folder_2a = item / "2A"
                    if folder_2a.exists():
                        items.append({
                            "name": item.name,
                            "path": str(item),
                            "type": "folder"
                        })
            else:
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "folder" if item.is_dir() else "file"
                })
        
        return jsonify({
            "items": items,
            "current_path": str(path),
            "parent_path": str(path.parent) if path.parent != path else None
        })
    except PermissionError:
        return jsonify({"error": "Permission denied"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def open_browser():
    """Open browser after server starts"""
    webbrowser.open('http://localhost:5000')


if __name__ == '__main__':
    print("\n" + "="*50)
    print("   KOSMIK - Arxivlash Tizimi")
    print("="*50)
    print(f"\n   Frontend: {FRONTEND_DIR}")
    print("   Server:   http://localhost:5000")
    print("\n   Opening browser...")
    print("="*50 + "\n")
    

    threading.Timer(1.5, open_browser).start()
    
    app.run(debug=False, port=5000, threaded=True)
