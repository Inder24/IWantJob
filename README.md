# Job Search Tool

Simple full-stack tool to upload a resume, extract skills/search terms, and run AI-based ATS scoring + suggestions.

## What works right now

- JWT auth (`register`, `login`, `me`, `refresh`)
- Resume PDF upload (max 10MB)
- Background resume parsing
- Skill, company, degree, and contact extraction
- Auto-generated search terms
- AI trigger button: **Check ATS Score via AI**
- ATS score + improvement suggestions persisted with timestamp
- Resume dedupe by `content_hash` (same resume is reused, not duplicated)
- LinkedIn integration (phase-1): fetch + normalize + store jobs
- Indeed integration (phase-1): fetch + normalize + store jobs
- Foundit integration (phase-1): fetch + normalize + store jobs
- Google Jobs integration (phase-1): fetch + normalize + store jobs
- Role-first auto-search with top-10 ranking + freshness
- Work authorization mode toggle (`singapore_pr` / `work_visa`)
- Admin DB Explorer UI at `/admin/`
- Simple HTML/CSS/JS frontend
- Backend tests (focused suite passing)

## Current architecture

- Backend: FastAPI + Python
- Data layer: SQLite (Mongo-like adapter API)
- File storage: SQLite `gridfs` table (BLOB)
- NLP: spaCy + rule-based extraction
- AI enrichment/scoring: Gemini (`gemini-2.5-flash`, optional)

## Setup

### 1) Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs:
- `http://localhost:8000/docs`

### 2) Frontend

Serve `frontend/` as static files (or open `frontend/index.html` directly).
Frontend expects backend at:
- `http://localhost:8000/api`
- Admin page:
  - `http://localhost:3000/admin/`

## Environment variables (`backend/.env`)

Minimal required:

- `JWT_SECRET`

Only if using ATS AI button:

- `ENABLE_AGENT_EXTRACTION=true`
- `GEMINI_API_KEY=...`

Everything else is optional (defaults are already in code).  
Use `backend/.env.example` as your starting template.

### Database

The app currently runs on local SQLite (`backend/job_search.db`) via `app/database.py`.

## API summary

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/refresh`

### Resume

- `POST /api/resume/upload`
- `GET /api/resume/me`
- `POST /api/resume/me/ats-score` ← trigger ATS scoring via AI
- `DELETE /api/resume/me`

### Jobs

- `POST /api/jobs/linkedin/search` ← fetch from LinkedIn via SerpAPI and upsert locally
- `POST /api/jobs/indeed/search` ← fetch Indeed.sg jobs via SerpAPI Google engine
- `POST /api/jobs/foundit/search` ← fetch Foundit.sg jobs via SerpAPI Google engine
- `POST /api/jobs/google-jobs/search` ← fetch jobs via SerpAPI Google Jobs engine
- `POST /api/jobs/auto-search` ← run resume-skill-driven strategy across all sources
- `POST /api/jobs/track-view` ← track explicit job click/view (`user_job_views`)
- `GET /api/jobs/me` ← list stored jobs from local DB

## How it works (current flow)

1. User logs in and uploads a PDF resume.
2. Backend computes `content_hash`; if same hash exists for user, existing record is reused.
3. Background parser extracts raw text + contact + skills + companies + education.
4. Search terms are generated from job titles and top technical skills.
5. Optional Gemini pass enriches output and provides:
   - `resume_score` (0-100)
   - `improvement_suggestions`
6. UI shows parsed sections, score, suggestions, and `last_ats_checked_at`.

## LinkedIn integration (phase-1)

Set in `.env`:

- `SERPAPI_API_KEY=...`

Optional:

- `LINKEDIN_MAX_RESULTS=20`
- `LINKEDIN_HTTP_TIMEOUT_SECONDS=20`

Example call:

```bash
curl -X POST http://localhost:8000/api/jobs/linkedin/search \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"python developer","location":"Singapore","page":0}'
```

## Indeed + Foundit integration (phase-1)

Uses SerpAPI Google search with Singapore targeting (`gl=sg`).

Examples:

```bash
curl -X POST http://localhost:8000/api/jobs/indeed/search \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"data analyst","location":"Singapore","page":0}'
```

```bash
curl -X POST http://localhost:8000/api/jobs/foundit/search \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"backend engineer","location":"Singapore","page":0}'
```

## Auto search strategy endpoint

Uses role-first strategy (`role_terms` + job titles), then searches LinkedIn + Indeed + Foundit + Google Jobs, dedupes, and ranks by match score.  
Top 10 returned jobs are freshness-aware: jobs already surfaced today are deprioritized.

```bash
curl -X POST http://localhost:8000/api/jobs/auto-search \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"location":"Singapore","max_terms":6,"per_source_page":0,"max_total_requests":12,"max_concurrency":3,"work_auth_mode":"singapore_pr","employment_mode":"all"}'
```

Search budget logic:
- planned requests = `min(max_total_requests, max_terms * 4_sources)`
- default request cap = `12`
- default parallelism cap = `3`
- current frontend uses `max_total_requests=24` and `max_concurrency=4` for broader coverage

Work authorization mode:
- `work_auth_mode: "singapore_pr"` (default): current ranking behavior, no strict exclusion.
- `work_auth_mode: "work_visa"`: filters out jobs that mention non-sponsorship or SG/PR-only eligibility (e.g. `pr only`, `no sponsorship`, `work pass not provided`) before dedupe/top-10 ranking.

Employment mode:
- `employment_mode: "all"` (default): no contract/full-time filter.
- `employment_mode: "full_time"`: filters out contract-style postings.
- `employment_mode: "contract"`: keeps contract-style postings only.

Response metadata now includes:
- `work_auth_mode`
- `work_auth_filtered_out`
- `employment_mode`
- `employment_filtered_out`
- `source_candidate_counts` (how many each source returned before top-10)
- `top_source_counts` (how many from each source made top-10)

Skill quality:
- skills are sanitized before save (removes bracket artifacts)
- optional Gemini validation keeps only resume-evidenced, role-relevant skills

## Notes

- Do not commit secrets (`.env` should stay local).
- MongoDB Atlas is planned; current stable runtime uses SQLite adapter.
- Job scraping/tracking modules are still pending.

## Admin DB Explorer

- `GET /api/admin/tables` → lists available tables + column metadata.
- `GET /api/admin/tables/{table_name}/rows?limit=50` → returns table rows (limit: 1..200).
- Available at frontend route **`/admin/`**.
