import asyncio
from datetime import datetime
from typing import Dict, Optional, Any

from app.models.schemas import (
    WorkflowState,
    AnalysisInput,
    WorkflowStage,
    StageInfo,
    StageStatus,
)
from app.workflow.stages import StageExecutor
from app.utils.cache import CacheManager


class WorkflowEngine:
    STAGES = [
        WorkflowStage.SCOPE,
        WorkflowStage.COLLECT,
        WorkflowStage.CLEAN,
        WorkflowStage.CLASSIFY,
        WorkflowStage.EVALUATE,
        WorkflowStage.PLAN,
        WorkflowStage.PRD,
        WorkflowStage.TESTGEN,
        WorkflowStage.VALIDATE,
        WorkflowStage.PRESENT,
    ]

    def __init__(self):
        self._states: Dict[str, WorkflowState] = {}
        self._cache = CacheManager()

    def get_state(self, job_id: str) -> Optional[WorkflowState]:
        return self._states.get(job_id)

    def _build_initial_state(self, job_id: str, input_data: AnalysisInput) -> WorkflowState:
        stages = [
            StageInfo(stage=s, status=StageStatus.PENDING)
            for s in self.STAGES
        ]
        return WorkflowState(job_id=job_id, input=input_data, stages=stages)

    async def run(self, job_id: str, input_data: AnalysisInput) -> WorkflowState:
        state = self._build_initial_state(job_id, input_data)
        self._states[job_id] = state
        executor = StageExecutor(state)

        for idx, stage_enum in enumerate(self.STAGES):
            state.current_stage_index = idx
            stage_info = state.stages[idx]
            stage_info.status = StageStatus.RUNNING
            stage_info.started_at = datetime.utcnow()
            stage_info.message = f"Running {stage_enum.value}..."
            self._persist(state)

            try:
                method = getattr(executor, stage_enum.value)
                result = await method()
                stage_info.status = StageStatus.COMPLETED
                stage_info.result = result
                stage_info.message = self._completion_message(stage_enum, result)
                stage_info.completed_at = datetime.utcnow()
            except Exception as e:
                stage_info.status = StageStatus.FAILED
                stage_info.message = str(e)
                stage_info.completed_at = datetime.utcnow()
                state.error = str(e)
                self._persist(state)
                raise

            self._persist(state)
            # Small yield to allow status polling
            await asyncio.sleep(0.05)

        return state

    def _persist(self, state: WorkflowState):
        self._cache.save_workflow(state.job_id, state.model_dump(mode="json"))

    def _completion_message(self, stage: WorkflowStage, result: Dict[str, Any]) -> str:
        messages = {
            WorkflowStage.SCOPE: f"Scope defined for app {result.get('app_id', 'N/A')}",
            WorkflowStage.COLLECT: f"Collected {result.get('review_count', 0)} reviews",
            WorkflowStage.CLEAN: f"Cleaned to {result.get('review_count_after_clean', 0)} reviews",
            WorkflowStage.CLASSIFY: f"Discovered {result.get('topic_count', 0)} topics",
            WorkflowStage.EVALUATE: f"Generated {result.get('finding_count', 0)} findings",
            WorkflowStage.PLAN: f"Planned {result.get('version_count', 0)} versions",
            WorkflowStage.PRD: f"Generated {result.get('requirement_count', 0)} requirements",
            WorkflowStage.TESTGEN: f"Generated {result.get('test_case_count', 0)} test cases",
            WorkflowStage.VALIDATE: f"Validation: {result.get('issue_count', 0)} issues",
            WorkflowStage.PRESENT: "Report ready",
        }
        return messages.get(stage, f"Completed {stage.value}")
