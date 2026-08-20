import asyncio
from typing import Dict, Any, Optional


class JobEventEmitter:
    """Simple per-job event emitter for SSE progress streaming."""

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Create or return an existing queue for a job."""
        q = asyncio.Queue(maxsize=200)
        self._queues[job_id] = q
        return q

    def emit(self, job_id: Optional[str], event: Dict[str, Any]) -> None:
        """Emit an event to all subscribers of a job."""
        if not job_id:
            return
        q = self._queues.get(job_id)
        if not q:
            return
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event if queue is full
            try:
                q.get_nowait()
                q.put_nowait(event)
            except asyncio.QueueEmpty:
                pass

    def unsubscribe(self, job_id: str) -> None:
        self._queues.pop(job_id, None)


event_emitter = JobEventEmitter()
