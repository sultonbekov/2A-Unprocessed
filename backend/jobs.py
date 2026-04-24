import threading

_JOBS = {}
_LOCK = threading.Lock()


def create_job(job_id: str) -> None:
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "processed_bytes": 0,
            "processed_files": 0,
            "completed_viloyats": 0,
        }


def update_job(job_id: str, **fields) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(fields)


def tick_progress(job_id: str, viloyat_name: str,
                  bytes_delta: int, files_delta: int) -> None:
    with _LOCK:
        if job_id in _JOBS:
            j = _JOBS[job_id]
            j["processed_bytes"] = j.get("processed_bytes", 0) + bytes_delta
            j["processed_files"] = j.get("processed_files", 0) + files_delta
            j["current_viloyat"] = viloyat_name


def mark_viloyat_done(job_id: str) -> None:
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["completed_viloyats"] = \
                _JOBS[job_id].get("completed_viloyats", 0) + 1


def get_job(job_id: str):
    with _LOCK:
        return dict(_JOBS[job_id]) if job_id in _JOBS else None
