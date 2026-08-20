from typing import Dict, Optional

from app.graph.workflow import app_graph
from app.graph.state import PipelineState
from app.utils.events import event_emitter


class GraphRunner:
    def __init__(self):
        self._states: Dict[str, PipelineState] = {}

    def get_state(self, job_id: str) -> Optional[PipelineState]:
        return self._states.get(job_id)

    @staticmethod
    def _ensure_state(obj) -> PipelineState:
        if isinstance(obj, PipelineState):
            return obj
        if isinstance(obj, dict):
            return PipelineState(**obj)
        raise ValueError(f"Unexpected state type: {type(obj)}")

    async def run(self, job_id: str, initial_state: PipelineState) -> PipelineState:
        initial_state.job_id = job_id
        self._states[job_id] = initial_state
        event_emitter.subscribe(job_id)
        try:
            final_state = await app_graph.ainvoke(initial_state)
            state = self._ensure_state(final_state)
            self._states[job_id] = state
            event_emitter.emit(job_id, {"type": "completed", "stage": state.stage})
            return state
        except Exception as e:
            initial_state.error = str(e)
            self._states[job_id] = initial_state
            event_emitter.emit(job_id, {"type": "error", "error": str(e)})
            return initial_state
        finally:
            # Keep queue around briefly so late SSE connect can read final state;
            # unsubscribe is handled by SSE endpoint disconnect.
            pass


_runner = GraphRunner()


def get_runner() -> GraphRunner:
    return _runner
