import os
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models.schemas import (
    AnalysisInput,
    StartAnalysisResponse,
    WorkflowStatusResponse,
    ExportRequest,
)
from app.graph.runner import get_runner
from app.graph.state import PipelineState
from app.graph import chains
from app.services.export import ExportService
from app.utils.cache import CacheManager


_jobs: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data/cache", exist_ok=True)
    os.makedirs("data/uploads", exist_ok=True)
    os.makedirs("data/exports", exist_ok=True)
    os.makedirs("backend/sample_data", exist_ok=True)
    yield
    _jobs.clear()


app = FastAPI(
    title="App Review Analysis Agent",
    description="LangGraph-powered agent that transforms App Store reviews into PRDs and insights.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


STAGES = [
    ("scope", "Scope defined"),
    ("collect", "Reviews collected"),
    ("clean", "Reviews cleaned"),
    ("classify", "Topics discovered"),
    ("evaluate", "Findings generated"),
    ("plan", "Versions planned"),
    ("prd", "PRD generated"),
    ("validate", "Traceability validated"),
    ("present", "Report ready"),
]


def _build_stages(state) -> List[Dict[str, Any]]:
    if isinstance(state, dict):
        state = PipelineState(**state)
    stage_order = ["scope", "collect", "clean", "classify", "evaluate", "plan", "prd", "validate", "present"]
    current_stage = state.stage or "pending"
    current_idx = stage_order.index(current_stage) if current_stage in stage_order else -1
    stages = []
    for i, (sid, label) in enumerate(STAGES):
        if i < current_idx:
            status = "completed"
        elif i == current_idx:
            status = "running" if state.validation_status not in ("COMPLETED", "PASSED", "PARTIAL") else "completed"
        else:
            status = "pending"
        stages.append({
            "stage": sid,
            "status": status,
            "message": label,
            "result": {},
        })
    if state.error:
        stages[current_idx]["status"] = "failed"
        stages[current_idx]["message"] = state.error
    return stages


@app.post("/api/analyze", response_model=StartAnalysisResponse)
async def start_analysis(input_data: AnalysisInput, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"state": None}

    initial_state = PipelineState(
        app_url=input_data.app_url,
        app_id=input_data.app_id,
        user_goal=input_data.analysis_goal or "Improve the app based on user feedback",
    )
    if input_data.uploaded_file:
        initial_state.app_url = input_data.uploaded_file

    background_tasks.add_task(_run_workflow, job_id, initial_state)
    return StartAnalysisResponse(job_id=job_id, status="started")


async def _run_workflow(job_id: str, initial_state: PipelineState):
    runner = get_runner()
    try:
        state = await runner.run(job_id, initial_state)
        _jobs[job_id]["state"] = state
    except Exception as e:
        initial_state.error = str(e)
        _jobs[job_id]["state"] = initial_state


@app.get("/api/analyze/{job_id}/status", response_model=WorkflowStatusResponse)
async def get_status(job_id: str):
    runner = get_runner()
    state = runner.get_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    stages = _build_stages(state)
    completed = sum(1 for s in stages if s["status"] == "completed")
    progress_pct = (completed / len(stages) * 100) if stages else 0
    current = state.stage
    return WorkflowStatusResponse(
        job_id=job_id,
        current_stage=current,
        stages=stages,
        progress_pct=progress_pct,
        error=state.error,
    )


@app.get("/api/analyze/{job_id}/result")
async def get_result(job_id: str):
    runner = get_runner()
    state = runner.get_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if isinstance(state, dict):
        return state
    return state.model_dump(mode="json")


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".csv", ".json"):
        raise HTTPException(status_code=400, detail="Only .csv or .json files are supported")
    upload_dir = "data/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, f"{uuid.uuid4().hex}{ext}")
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"path": path, "filename": file.filename}


@app.post("/api/chat/{job_id}")
async def chat(job_id: str, payload: Dict[str, Any]):
    runner = get_runner()
    state = runner.get_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if isinstance(state, dict):
        state = PipelineState(**state)

    messages = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    context = {
        "app_id": state.app_id,
        "user_goal": state.user_goal,
        "review_count": len(state.cleaned_reviews),
        "findings": [f.model_dump(mode="json") for f in state.findings],
        "version_plan": [v.model_dump(mode="json") for v in state.version_plan],
        "prd": state.prd,
        "summary": state.summary,
    }

    answer = await chains.chat_with_context(messages, context)
    return {"answer": answer}


@app.post("/api/export")
async def export_report(req: ExportRequest):
    runner = get_runner()
    state = runner.get_state(req.job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if isinstance(state, dict):
        state = PipelineState(**state)
    exporter = ExportService()
    output_path = await exporter.export(state, req.format)
    if req.format == "markdown":
        media_type = "text/markdown"
    elif req.format == "json":
        media_type = "application/json"
    else:
        media_type = "text/csv"
    return FileResponse(output_path, media_type=media_type, filename=os.path.basename(output_path))


@app.get("/api/sample-apps")
async def list_sample_apps():
    return {"apps": ["324684580", "284815942", "835198884"]}
