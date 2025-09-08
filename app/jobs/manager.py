from dataclasses import dataclass, field, asdict
from threading import Lock
from typing import Dict, Any, Optional, Tuple
import time

@dataclass
class JobState:
    status: str = "queued"
    progress: int = 0
    total: int = 0
    done: int = 0
    taxonomy: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

class JobsManager:
    def __init__(self):
        self._jobs: Dict[str, JobState] = {}
        self._lock = Lock()

    def set(self, job_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            state = self._jobs.get(job_id, JobState())
            for k, v in payload.items():
                setattr(state, k, v)
            state.updated_at = time.time()
            self._jobs[job_id] = state

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            if job_id in self._jobs:
                for k, v in kwargs.items():
                    setattr(self._jobs[job_id], k, v)
                self._jobs[job_id].updated_at = time.time()

    def get(self, job_id: str, default=None) -> Dict[str, Any] | None:
        with self._lock:
            s = self._jobs.get(job_id)
            return asdict(s) if s else default

    def all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {jid: asdict(s) for jid, s in self._jobs.items()}

    def find_active_for_taxonomy(self, taxonomy: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        with self._lock:
            for jid, s in self._jobs.items():
                if s.taxonomy == taxonomy and s.status in ("queued", "running"):
                    return jid, asdict(s)
            return None
