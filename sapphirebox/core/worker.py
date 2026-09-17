"""In-memory registry of in-flight download jobs.

Port of the `DOWNLOADS: Lazy<Mutex<HashMap<String, Value>>>` static in the
old commands/download.rs. A dict keyed by job id, one lock, same shape.
Runs jobs on background threads so the CLI (and, later, an API) can poll
progress without blocking.
"""
from __future__ import annotations

import threading
import uuid
from typing import Callable

from sapphirebox.core.models import DownloadJob

_jobs: dict[str, DownloadJob] = {}
_cancel_flags: set[str] = set()
_lock = threading.Lock()


class DownloadCancelled(Exception):
    """Raised from inside a download loop's on_progress callback once
    request_cancel() has flagged that job — run_in_background's wrapper
    catches this specially (status "cancelled", not "error")."""


def new_job() -> DownloadJob:
    job = DownloadJob(id=str(uuid.uuid4()))
    with _lock:
        _jobs[job.id] = job
    return job


def update(job_id: str, **fields) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)


def get(job_id: str) -> DownloadJob | None:
    with _lock:
        return _jobs.get(job_id)


def snapshot() -> list[DownloadJob]:
    with _lock:
        return list(_jobs.values())


def request_cancel(job_id: str) -> bool:
    """Flags a pending/running job for cancellation. The actual stop
    happens the next time that job's on_progress callback runs and raises
    DownloadCancelled — there's no way to interrupt a download loop that
    doesn't check in periodically, but every source's does (once per
    chapter/page, or once per second during an asdocs.net-style wait)."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None or job.status not in ("pending", "running"):
            return False
        _cancel_flags.add(job_id)
        return True


def is_cancel_requested(job_id: str) -> bool:
    with _lock:
        return job_id in _cancel_flags


def delete(job_id: str) -> bool:
    """Removes a job from the queue — for a still-running job this also
    requests cancellation first, so the background thread stops instead
    of finishing invisibly after its entry is gone. The cancel flag (if
    any) is left in place for the running thread to discover; it cleans
    up after itself in run_in_background's `finally` once it actually
    stops."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return False
        if job.status in ("pending", "running"):
            _cancel_flags.add(job_id)
        else:
            _cancel_flags.discard(job_id)
        del _jobs[job_id]
        return True


def run_in_background(job: DownloadJob, target: Callable[[], None]) -> threading.Thread:
    def _wrapped() -> None:
        try:
            update(job.id, status="running")
            target()
        except DownloadCancelled:
            update(job.id, status="cancelled", last_stdout="Cancelado")
        except Exception as exc:  # surfaced via job.error, never crashes the runner
            update(job.id, status="error", error=str(exc))
        finally:
            with _lock:
                _cancel_flags.discard(job.id)

    thread = threading.Thread(target=_wrapped, daemon=True)
    thread.start()
    return thread
