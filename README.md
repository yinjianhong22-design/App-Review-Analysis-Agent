# App-Review-Analysis-Agent

根据用户评论，分析总结痛点，做成需求文档。

A local, full-stack web application that transforms U.S. App Store user reviews into actionable product requirements, version roadmaps, and test cases — driven by an LLM-powered agent with full traceability.

## Features

- **U.S. App Store RSS Feed ingestion** (up to 500 text reviews per app)
- **CSV / JSON upload** for offline analysis and custom datasets
- **10-stage analysis pipeline** with real-time progress tracking
- **LLM-driven dynamic topic discovery** (no hard-coded categories)
- **Evidence-based findings** with confidence scores and conflict detection
- **PRD generation** linked back to original reviews
- **Test case synthesis** traceable to requirements
- **Interactive traceability graph** (Review → Finding → Requirement → Test Case)
- **Export** PRD as Markdown, test cases as CSV, full report as JSON
- **Offline mode** with bundled sample reviews

## Architecture

```
Frontend (React + Vite + Tailwind CSS)
  └─ Input Panel / Stage Navigator / Results Dashboard / Traceability Graph

Backend (Python FastAPI)
  └─ Workflow Engine → 10 stages → Data / Cleaning / LLM / Analysis / Planning / TestGen / Validation / Export

AI Layer (OpenAI-compatible API, e.g. OpenAI, DeepSeek)
  └─ Versioned prompts with JSON Schema structured output
```

## Quick Start

### 1. Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your API key
```

Example for **OpenAI**:

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
LLM_JSON_MODE=json_schema
```

Example for **DeepSeek** (default):

```env
OPENAI_API_KEY=your_deepseek_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
LLM_JSON_MODE=json_object
```

> **Note:** DeepSeek 目前对 OpenAI 的 `json_schema` strict 模式支持有限，因此默认使用 `json_object` 模式，并将 JSON Schema 注入到 System Prompt 中约束输出格式。

### 2. Start the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### 4. Run an analysis

- Enter a U.S. App Store URL (e.g. `https://apps.apple.com/us/app/example/id123456789`) or paste an App ID.
- Enter an analysis goal (e.g. `Improve subscription conversion`).
- Click **Start Analysis**.
- Or upload `backend/sample_data/sample_reviews.json` to run offline.

## 10-Stage Pipeline

| # | Stage | Method | Output |
|---|-------|--------|--------|
| 1 | Scope | Rule | Parsed app_id + goal |
| 2 | Collect | Rule | Reviews from RSS or upload |
| 3 | Clean | Rule | Deduplicated, normalized reviews |
| 4 | Classify | **LLM** | Dynamic topics + review classifications |
| 5 | Evaluate | **LLM** | Findings with evidence + conflicts |
| 6 | Plan | **LLM** | Version roadmap |
| 7 | PRD | **LLM** | Requirements with trace links |
| 8 | TestGen | **LLM + Rule** | Test cases traceable to requirements |
| 9 | Validate | Rule + LLM | Traceability matrix + assumption flags |
| 10 | Present | Rule | Dashboard + exports |

## Data Limitations

- Apple RSS Feed returns at most **500 text reviews** per app.
- Only reviews that include text are returned; star-only ratings are excluded.
- Analysis is limited to the U.S. App Store.

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/schemas.py
│   │   ├── services/
│   │   │   ├── data_collection.py
│   │   │   ├── cleaning.py
│   │   │   ├── ai_agent.py
│   │   │   ├── analysis.py
│   │   │   ├── planning.py
│   │   │   ├── testgen.py
│   │   │   ├── validation.py
│   │   │   └── export.py
│   │   ├── workflow/
│   │   │   ├── engine.py
│   │   │   └── stages.py
│   │   └── utils/
│   │       ├── cache.py
│   │       └── traceability.py
│   ├── prompts/
│   │   ├── classify_v1.0.txt
│   │   ├── evaluate_v1.0.txt
│   │   ├── plan_v1.0.txt
│   │   ├── prd_v1.0.txt
│   │   └── testgen_v1.0.txt
│   ├── sample_data/
│   │   └── sample_reviews.json
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── stores/workflowStore.ts
│   │   ├── components/
│   │   │   ├── InputPanel.tsx
│   │   │   ├── StageNavigator.tsx
│   │   │   ├── ResultsDashboard.tsx
│   │   │   ├── ReviewExplorer.tsx
│   │   │   ├── FindingCard.tsx
│   │   │   ├── TraceabilityGraph.tsx
│   │   │   └── ExportPanel.tsx
│   │   └── types/index.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/analyze` | Start analysis |
| GET | `/api/analyze/{job_id}/status` | Poll stage status |
| GET | `/api/analyze/{job_id}/result` | Get full result |
| POST | `/api/upload` | Upload CSV/JSON reviews |
| POST | `/api/export` | Export report |
| GET | `/api/sample-apps` | Sample App Store IDs |

## License

MIT
