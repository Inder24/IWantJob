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
- Simple HTML/CSS/JS frontend
- Backend tests (`17 passed`)

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

## How it works (current flow)

1. User logs in and uploads a PDF resume.
2. Backend computes `content_hash`; if same hash exists for user, existing record is reused.
3. Background parser extracts raw text + contact + skills + companies + education.
4. Search terms are generated from job titles and top technical skills.
5. Optional Gemini pass enriches output and provides:
   - `resume_score` (0-100)
   - `improvement_suggestions`
6. UI shows parsed sections, score, suggestions, and `last_ats_checked_at`.

## Notes

- Do not commit secrets (`.env` should stay local).
- MongoDB Atlas is planned; current stable runtime uses SQLite adapter.
- Job scraping/tracking modules are still pending.
