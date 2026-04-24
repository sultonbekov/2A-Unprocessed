# Server: input papkadan -> output papkaga arxivlashni boshqaradi

from pathlib import Path
import threading
import uuid
import webbrowser
import logging
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from archiver import run_archive_job, find_viloyats
from config import SERVER_PORT
import jobs

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / 'frontend'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path='')
CORS(app)

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)

@app.route('/api/validate', methods=['POST'])
def validate():
    data = request.get_json() or {}
    input_path = data.get('input_path', '').strip()

    if not input_path:
        return jsonify({"valid": False, "error": "Kirish yo'li ko'rsatilmagan"}), 400

    p = Path(input_path)
    if not p.exists():
        return jsonify({"valid": False, "error": "Yo'l topilmadi"})
    if not p.is_dir():
        return jsonify({"valid": False, "error": "Bu papka emas"})

    viloyats = find_viloyats(p)
    if not viloyats:
        return jsonify({
            "valid": False,
            "error": "Viloyatlar topilmadi (Unprocessed/2A strukturasi yo'q)",
        })

    return jsonify({
        "valid": True,
        "viloyat_count": len(viloyats),
        "viloyats": [{"name": v["name"]} for v in viloyats],
    })


@app.route('/api/archive', methods=['POST'])
def start_archive():
    data = request.get_json() or {}
    input_path = data.get('input_path', '').strip()
    output_path = data.get('output_path', '').strip()

    if not input_path or not output_path:
        return jsonify({
            "success": False,
            "error": "Kirish va chiqish yo'llarini ko'rsating",
        }), 400

    job_id = uuid.uuid4().hex
    jobs.create_job(job_id)

    thread = threading.Thread(
        target=run_archive_job,
        args=(job_id, input_path, output_path),
        daemon=True,
    )
    thread.start()
    logger.info(f"Arxivlash boshlandi: {job_id} | {input_path} -> {output_path}")

    return jsonify({"success": True, "job_id": job_id})


@app.route('/api/progress/<job_id>', methods=['GET'])
def progress(job_id):
    job = jobs.get_job(job_id)
    if not job:
        return jsonify({"error": "Ish topilmadi"}), 404

    total = job.get("total_bytes", 0)
    processed = job.get("processed_bytes", 0)
    job["percent"] = (processed / total * 100) if total > 0 else 0

    if job.get("start_time") and processed > 0 and total > 0:
        start = datetime.fromisoformat(job["start_time"])
        elapsed = (datetime.now() - start).total_seconds()
        speed = processed / elapsed if elapsed > 0 else 0
        remaining = (total - processed) / speed if speed > 0 else 0
        job["eta_seconds"] = int(remaining)
        job["current_speed"] = f"{speed / (1024 * 1024):.1f} MB/s"
        job["elapsed"] = int(elapsed)

    return jsonify(job)


def _open_browser():
    webbrowser.open(f'http://localhost:{SERVER_PORT}')


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("   KOSMIK - Arxivlash Tizimi (7z, parallel)")
    print("=" * 60)
    print(f"   Frontend: {FRONTEND_DIR}")
    print(f"   Server:   http://localhost:{SERVER_PORT}")
    print("=" * 60 + "\n")

    threading.Timer(1.0, _open_browser).start()

    app.run(debug=False, port=SERVER_PORT, threaded=True)
