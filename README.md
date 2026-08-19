# App-Review-Analysis-Agent

基于 U.S. App Store 用户评论，自动分析痛点、生成需求文档（PRD）与版本规划，并支持 Agent 对话追问的本地全栈应用。

A local, full-stack web application that transforms U.S. App Store user reviews into actionable findings, PRDs, and version roadmaps — powered by a **LangGraph + LangChain** agent with traceability guardrails and an interactive chat panel.

---

## Features

- **U.S. App Store RSS Feed ingestion** (up to 500 text reviews per app)
- **CSV / JSON upload** for offline analysis and custom datasets
- **LangGraph-driven analysis pipeline** with 7 nodes and self-correction loop
- **LLM-driven dynamic topic discovery** (no hard-coded categories)
- **Evidence-based findings** with confidence scores, conflict notes, and hypothesis flags
- **PRD generation** linked back to original reviews via `finding_ids` / `source_reviews`
- **Agent Chat panel** — ask follow-up questions against the analyzed context
- **Export** full report as JSON or PRD summary as Markdown
- **Offline mode** with bundled sample reviews

---

## Architecture

```
Frontend (React + Vite + Tailwind CSS)
  └─ Input Panel / Stage Navigator / Results Dashboard / Agent Chat

Backend (Python FastAPI + LangGraph)
  └─ LangGraph Workflow → 7 nodes → Data / Clean / Classify / Evaluate / Plan / PRD / Verify / Present

AI Layer (OpenAI-compatible API, e.g. DeepSeek / OpenAI)
  └─ LangChain ChatOpenAI + versioned prompts + JSON Object structured output
```

### LangGraph Workflow

```
fetch_and_clean ──► classify ──► evaluate ──► plan ──► prd ──► verify
                                                                  │
                                                                  ▼
                                                               present
                                                                  │
                                                                 END

verify 自检规则：
- 每个 Requirement 必须关联至少一个 Finding
- 每个 Finding 的 evidence_ids 和 Requirement 的 source_reviews 必须存在于已清洗的评论池中
- 若发现断裂或悬空引用：
  - retry_count < 2 时回到 prd 节点重新生成
  - 超过 2 次后标记为 PARTIAL 并进入 present 节点
- 无问题时 validation_status = PASSED → present
```

### Deterministic vs. LLM Boundaries

| Layer | Responsibility | Examples |
|-------|---------------|----------|
| **Rules** | Data fetching, cleaning, dedup, ID validation, traceability checks | RSS pagination, SHA fuzzy dedup, review_id existence checks |
| **Statistics** | Distribution, counts, ratings | Review count, rating histogram, support_count |
| **LLM** | Semantic understanding, topic discovery, synthesis, summarization | Dynamic topic discovery, finding statement, PRD scope_in/scope_out, chat answer |

---

## Quick Start

### 1. Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your API key
```

Example for **DeepSeek** (default):

```env
OPENAI_API_KEY=your_deepseek_api_key_here
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-v4-pro
LLM_JSON_MODE=json_object
```

Example for **OpenAI**:

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
LLM_JSON_MODE=json_schema
```

> **Note:** DeepSeek 目前对 OpenAI 的 `json_schema` strict 模式支持有限，因此默认使用 `json_object` 模式，并将 JSON Schema 约束注入到 System Prompt 中。

### 2. Start the backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
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

### 5. Chat with the Agent

After analysis completes, click **Ask Agent** to open the chat panel. You can ask questions like:

- "哪个痛点影响的用户最多？"
- "把 P0 需求整理成 Markdown"
- "这些发现之间有什么冲突？"

---

## Pipeline Stages

| # | Stage | Node | Method | Output |
|---|-------|------|--------|--------|
| 1 | Scope | — | Rule | Parsed `app_id` + `user_goal` |
| 2 | Collect | `fetch_and_clean` | Rule | Reviews from RSS or upload |
| 3 | Clean | `fetch_and_clean` | Rule | Deduplicated, normalized reviews |
| 4 | Classify | `classify` | **LLM** | Dynamic topics + review classifications |
| 5 | Evaluate | `evaluate` | **LLM + Rule** | Findings with evidence + conflict notes |
| 6 | Plan | `plan` | **LLM** | Version roadmap |
| 7 | PRD | `prd` | **LLM** | Requirements with trace links |
| 8 | Validate | `verify` | Rule | Traceability checks + retry loop |
| 9 | Present | `present` | **LLM** | Final summary + report |

---

## Traceability & Guardrails

- **Finding → Review:** every `Finding.evidence_ids` must point to an existing review; `support_count < 3` is automatically marked as `is_hypothesis = true`.
- **Requirement → Finding:** every `Requirement.finding_ids` must point to an existing finding.
- **Requirement → Review:** `Requirement.source_reviews` are checked against the cleaned review pool.
- **Self-correction:** `verify_node` detects dangling links and loops back to `prd_node` up to 2 times before falling back to `PARTIAL`.

---

## Data Limitations

- Apple RSS Feed returns at most **500 text reviews** per app.
- Only reviews that include text are returned; star-only ratings are excluded.
- Analysis is limited to the U.S. App Store.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry + chat endpoint
│   │   ├── config.py               # Pydantic Settings from .env
│   │   ├── models/schemas.py       # API request/response schemas
│   │   ├── graph/
│   │   │   ├── state.py            # Pydantic state models
│   │   │   ├── nodes.py            # 7 LangGraph nodes
│   │   │   ├── chains.py           # LangChain LLM wrappers
│   │   │   ├── workflow.py         # LangGraph compile + routing
│   │   │   └── runner.py           # Async runner + state storage
│   │   ├── services/
│   │   │   ├── data_collection.py  # RSS / file collectors
│   │   │   ├── cleaning.py         # Deterministic cleaning
│   │   │   └── export.py           # JSON / Markdown export
│   │   └── utils/
│   │       └── cache.py            # Local file cache
│   ├── prompts/
│   │   ├── classify_v1.0.txt
│   │   ├── evaluate_v1.0.txt
│   │   ├── plan_v1.0.txt
│   │   ├── prd_v1.0.txt
│   │   └── summary_v1.0.txt
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
│   │   │   └── ChatPanel.tsx
│   │   └── types/index.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/analyze` | Start analysis |
| GET | `/api/analyze/{job_id}/status` | Poll stage status |
| GET | `/api/analyze/{job_id}/result` | Get full result |
| POST | `/api/upload` | Upload CSV/JSON reviews |
| POST | `/api/export` | Export report (json / markdown) |
| POST | `/api/chat/{job_id}` | Chat with analysis context |
| GET | `/api/sample-apps` | Sample App Store IDs |

---

## License

MIT
