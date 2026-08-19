from typing import Dict, Optional

from app.graph.workflow import app_graph
from app.graph.state import PipelineState


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
        self._states[job_id] = initial_state
        try:
            final_state = await app_graph.ainvoke(initial_state)
            state = self._ensure_state(final_state)
            self._states[job_id] = state
            return state
        except Exception as e:
            initial_state.error = str(e)
            self._states[job_id] = initial_state
            return initial_state


_runner = GraphRunner()


def get_runner() -> GraphRunner:
    return _runner
