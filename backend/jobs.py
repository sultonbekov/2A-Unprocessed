"""
KOSMIK Arxivlash - Ishlarni boshqarish moduli
Har bir arxivlash ishi (job) xotirada saqlanadi va progress kuzatiladi.
"""

import threading

# Barcha faol ishlar shu lug'atda saqlanadi: {job_id: {...}}
_JOBS = {}

# Bir nechta thread bir vaqtda yozishi mumkin, shuning uchun lock kerak
_LOCK = threading.Lock()


def create_job(job_id: str) -> None:
    """Yangi ish yaratadi va boshlang'ich holatga keltiradi"""
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "processed_bytes": 0,
            "processed_files": 0,
            "completed_viloyats": 0,
        }


def update_job(job_id: str, **fields) -> None:
    """Ish ma'lumotlarini yangilaydi (status, xatolik va h.k.)"""
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(fields)


def tick_progress(job_id: str, viloyat_name: str,
                  bytes_delta: int, files_delta: int) -> None:
    """Progressni oshiradi - har bir fayl arxivlanganda chaqiriladi"""
    with _LOCK:
        if job_id in _JOBS:
            j = _JOBS[job_id]
            j["processed_bytes"] = j.get("processed_bytes", 0) + bytes_delta
            j["processed_files"] = j.get("processed_files", 0) + files_delta
            j["current_viloyat"] = viloyat_name


def mark_viloyat_done(job_id: str) -> None:
    """Bitta viloyat to'liq arxivlangandan keyin chaqiriladi"""
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["completed_viloyats"] = \
                _JOBS[job_id].get("completed_viloyats", 0) + 1


def get_job(job_id: str):
    """Ishning hozirgi holatini nusxa sifatida qaytaradi"""
    with _LOCK:
        return dict(_JOBS[job_id]) if job_id in _JOBS else None
