import os
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from app.config import get_settings
from app.models.schemas import (
    AnalysisInput,
    StartAnalysisResponse,
    WorkflowStatusResponse,
    ExportRequest,
)
from app.workflow.engine import WorkflowEngine
from app.services.export import ExportService
from app.utils.cache import CacheManager


# In-memory job registry (replace with DB in production)
_jobs: Dict[str, Dict[str, Any]] = {}
_engine: WorkflowEngine = WorkflowEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    os.makedirs("data/cache", exist_ok=True)
    os.makedirs("backend/sample_data", exist_ok=True)
    yield
    # shutdown
    _jobs.clear()


app = FastAPI(
    title="App Review Analysis Agent",
    description="Transform App Store reviews into actionable PRDs, roadmaps, and test cases.",
    version="0.1.0",
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


@app.post("/api/analyze", response_model=StartAnalysisResponse)
async def start_analysis(input_data: AnalysisInput, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"state": None, "task": None}
    background_tasks.add_task(_run_workflow, job_id, input_data)
    return StartAnalysisResponse(job_id=job_id, status="started")


async def _run_workflow(job_id: str, input_data: AnalysisInput):
    try:
        state = await _engine.run(job_id, input_data)
        _jobs[job_id]["state"] = state
    except Exception as e:
        if job_id in _jobs:
            _jobs[job_id]["error"] = str(e)


@app.get("/api/analyze/{job_id}/status", response_model=WorkflowStatusResponse)
async def get_status(job_id: str):
    state = _engine.get_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    total = len(state.stages)
    completed = sum(1 for s in state.stages if s.status == "completed")
    progress_pct = (completed / total * 100) if total else 0
    current = state.stages[state.current_stage_index] if state.current_stage_index < total else None
    return WorkflowStatusResponse(
        job_id=job_id,
        current_stage=current.stage if current else None,
        stages=state.stages,
        progress_pct=progress_pct,
        error=state.error,
    )


@app.get("/api/analyze/{job_id}/result")
async def get_result(job_id: str):
    state = _engine.get_state(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
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


@app.post("/api/export")
async def export_report(req: ExportRequest):
    state = _engine.get_state(req.job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
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
    return {"apps": ["324684580", "284815942", "835198884"]}  # Sample App Store IDs
