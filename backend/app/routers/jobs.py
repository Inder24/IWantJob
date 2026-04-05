"""
Jobs router for multi-source search and persistence.
"""
import asyncio
from datetime import datetime
import uuid
from typing import Dict, List, Literal, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import requests

from app.database import get_database
from app.routers.auth import get_current_user
from app.services.linkedin_search import linkedin_search_service
from app.services.indeed_search import indeed_search_service
from app.services.foundit_search import foundit_search_service
from app.services.google_jobs_search import google_jobs_search_service


router = APIRouter()


class LinkedInSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    location: str = Field(default="", max_length=120)
    page: int = Field(default=0, ge=0, le=10)


class GenericSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200)
    location: str = Field(default="", max_length=120)
    page: int = Field(default=0, ge=0, le=10)


class AutoSearchRequest(BaseModel):
    location: str = Field(default="Singapore", max_length=120)
    max_terms: int = Field(default=6, ge=1, le=12)
    per_source_page: int = Field(default=0, ge=0, le=2)
    max_total_requests: int = Field(default=12, ge=1, le=36)
    max_concurrency: int = Field(default=3, ge=1, le=6)
    work_auth_mode: Literal["singapore_pr", "work_visa"] = Field(default="singapore_pr")


def _normalize_job_url(url: str) -> str:
    return (url or "").strip()


def _best_job_url(job: dict) -> str:
    detail_url = str(job.get("detail_url") or "").strip()
    if detail_url:
        return detail_url
    return _normalize_job_url(str(job.get("url") or ""))


def _clean_term(value: str) -> str:
    return " ".join((value or "").lower().strip().split())


def _build_query_terms(resume: dict, max_terms: int) -> List[str]:
    parsed = (resume or {}).get("parsed_data") or {}
    search_terms = resume.get("search_terms") or []
    role_terms = parsed.get("role_terms") or []
    experience = parsed.get("experience") or []

    titles: List[str] = []
    for exp in experience:
        title = (exp or {}).get("title", "").strip()
        if title:
            titles.append(title)

    candidates: List[str] = []
    candidates.extend(role_terms[:8])
    candidates.extend(search_terms[:4])
    candidates.extend(titles[:4])
    candidates.extend(["software engineer", "backend engineer", "data analyst", "data engineer"])

    # Add seniority variants for broader role search.
    seniority_variants: List[str] = []
    for term in list(candidates):
        t = term.strip()
        low = t.lower()
        if not t:
            continue
        if low.startswith(("senior ", "lead ", "principal ", "staff ")):
            continue
        seniority_variants.append(f"senior {t}")
        seniority_variants.append(f"lead {t}")
    candidates.extend(seniority_variants)

    deduped: List[str] = []
    seen = set()
    for term in candidates:
        cleaned = _clean_term(term)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(term.strip())
        if len(deduped) >= max_terms:
            break
    return deduped


def _score_job(job: dict, terms: List[str], resume_skills: List[str], preferred_location: str) -> int:
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    location = (job.get("location") or "").lower()
    text = f"{title} {desc}"

    score = 0
    for term in terms:
        t = _clean_term(term)
        if t and t in text:
            score += 15

    for skill in resume_skills[:20]:
        s = _clean_term(str(skill))
        if s and s in text:
            score += 5

    pref = _clean_term(preferred_location)
    if pref and pref in location:
        score += 20
    if "remote" in location:
        score += 6
    return min(score, 100)


WORK_VISA_EXCLUSION_PHRASES = (
    "singaporean only",
    "singaporeans only",
    "singapore citizen only",
    "singapore citizen",
    "singapore pr only",
    "pr only",
    "citizens only",
    "no sponsorship",
    "not sponsoring",
    "without sponsorship",
    "work pass not provided",
    "ep not provided",
    "spass not provided",
    "s pass not provided",
)


def _is_work_visa_ineligible(job: dict) -> bool:
    title = _clean_term(str(job.get("title") or ""))
    description = _clean_term(str(job.get("description") or ""))
    combined_text = f"{title} {description}".strip()
    if not combined_text:
        return False
    return any(phrase in combined_text for phrase in WORK_VISA_EXCLUSION_PHRASES)


async def _upsert_jobs(db, platform: str, jobs: List[dict], query: str, location: str):
    inserted = 0
    updated = 0
    saved_ids: List[str] = []

    for job in jobs:
        existing = await db.jobs.find_one({"platform": platform, "job_id": job["job_id"]})
        if not existing and _best_job_url(job):
            existing = await db.jobs.find_one({"platform": platform, "url": _best_job_url(job)})

        if existing:
            await db.jobs.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "title": job["title"],
                        "company": job["company"],
                        "location": job.get("location", ""),
                        "description": job.get("description", ""),
                        "url": _best_job_url(job),
                        "posted_date": job.get("posted_date"),
                        "scraped_at": datetime.utcnow().isoformat(),
                    }
                },
            )
            updated += 1
            saved_ids.append(existing["_id"])
            continue

        new_id = str(uuid.uuid4())
        await db.jobs.insert_one(
            {
                "_id": new_id,
                "platform": platform,
                "job_id": job["job_id"],
                "title": job["title"],
                "company": job["company"],
                "location": job.get("location", ""),
                "description": job.get("description", ""),
                "url": _best_job_url(job),
                "posted_date": job.get("posted_date"),
                "scraped_at": datetime.utcnow().isoformat(),
            }
        )
        inserted += 1
        saved_ids.append(new_id)

    return {
        "message": f"{platform.title()} jobs fetched successfully",
        "query": query,
        "location": location,
        "fetched_count": len(jobs),
        "inserted_count": inserted,
        "updated_count": updated,
        "job_ids": saved_ids,
    }


@router.post("/linkedin/search")
async def linkedin_search(
    payload: LinkedInSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search LinkedIn jobs and upsert into local jobs table."""
    del current_user  # endpoint is protected; user context reserved for future per-user filtering
    db = get_database()

    try:
        jobs = linkedin_search_service.search_jobs(
            query=payload.query.strip(),
            location=payload.location.strip(),
            page=payload.page,
        )
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"LinkedIn search failed: {str(exc)}")

    return await _upsert_jobs(db, "linkedin", jobs, payload.query, payload.location)


@router.post("/indeed/search")
async def indeed_search(
    payload: GenericSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search Indeed jobs and upsert into local jobs table."""
    del current_user
    db = get_database()
    try:
        jobs = indeed_search_service.search_jobs(
            query=payload.query.strip(),
            location=payload.location.strip(),
            page=payload.page,
        )
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Indeed search failed: {str(exc)}")
    return await _upsert_jobs(db, "indeed", jobs, payload.query, payload.location)


@router.post("/foundit/search")
async def foundit_search(
    payload: GenericSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search Foundit jobs and upsert into local jobs table."""
    del current_user
    db = get_database()
    try:
        jobs = foundit_search_service.search_jobs(
            query=payload.query.strip(),
            location=payload.location.strip(),
            page=payload.page,
        )
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Foundit search failed: {str(exc)}")
    return await _upsert_jobs(db, "foundit", jobs, payload.query, payload.location)


@router.post("/google-jobs/search")
async def google_jobs_search(
    payload: GenericSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Search Google Jobs and upsert into local jobs table."""
    del current_user
    db = get_database()
    try:
        jobs = google_jobs_search_service.search_jobs(
            query=payload.query.strip(),
            location=payload.location.strip(),
            page=payload.page,
        )
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Google Jobs search failed: {str(exc)}")
    return await _upsert_jobs(db, "google_jobs", jobs, payload.query, payload.location)


@router.get("/me")
async def list_jobs(current_user: dict = Depends(get_current_user), limit: int = 50):
    """List latest jobs from local store."""
    del current_user
    db = get_database()
    items = await db.jobs.find({}, limit=min(max(limit, 1), 100), order_by="scraped_at", desc=True)
    return {"count": len(items), "jobs": items}


@router.post("/auto-search")
async def auto_search_jobs(
    payload: AutoSearchRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Run multi-source job search strategy using current user's extracted resume skills/terms.
    """
    db = get_database()
    resume = await db.resumes.find_one({"user_id": current_user["_id"]})
    if not resume:
        raise HTTPException(status_code=404, detail="No resume found. Upload resume first.")
    if resume.get("parsing_status") != "completed":
        raise HTTPException(status_code=400, detail="Resume parsing not completed yet.")

    terms = _build_query_terms(resume, payload.max_terms)
    if not terms:
        raise HTTPException(status_code=400, detail="No search terms available from resume.")

    all_results: List[Tuple[str, str, dict]] = []
    failures: List[str] = []

    source_functions = (
        ("linkedin", linkedin_search_service.search_jobs),
        ("indeed", indeed_search_service.search_jobs),
        ("foundit", foundit_search_service.search_jobs),
        ("google_jobs", google_jobs_search_service.search_jobs),
    )
    search_plan: List[Tuple[str, str]] = []
    for term in terms:
        for source_name, _ in source_functions:
            search_plan.append((source_name, term))

    max_total_requests = min(payload.max_total_requests, len(search_plan))
    search_plan = search_plan[:max_total_requests]
    max_concurrency = min(payload.max_concurrency, max_total_requests)
    semaphore = asyncio.Semaphore(max_concurrency)
    fn_map = {name: fn for name, fn in source_functions}

    async def _run_search_call(source_name: str, term: str):
        async with semaphore:
            jobs = await asyncio.to_thread(
                fn_map[source_name],
                term,
                payload.location,
                payload.per_source_page,
            )
            return source_name, term, jobs

    tasks = [_run_search_call(source_name, term) for source_name, term in search_plan]
    search_outputs = await asyncio.gather(*tasks, return_exceptions=True)

    for item in search_outputs:
        if isinstance(item, Exception):
            failures.append(str(item))
            continue
        source_name, term, jobs = item
        if not jobs:
            continue
        try:
            await _upsert_jobs(db, source_name, jobs, term, payload.location)
            for job in jobs:
                all_results.append((source_name, term, job))
        except Exception as exc:
            failures.append(f"{source_name}:{term} -> {str(exc)}")

    resume_skills = ((resume.get("parsed_data") or {}).get("skills") or [])
    ranked: List[Dict[str, object]] = []
    for source_name, term, job in all_results:
        ranked.append(
            {
                **job,
                "source_query": term,
                "match_score": _score_job(job, terms, resume_skills, payload.location),
                "platform": source_name,
            }
        )
    filtered_out_count = 0
    filtered_ranked = ranked
    if payload.work_auth_mode == "work_visa":
        filtered_ranked = [job for job in ranked if not _is_work_visa_ineligible(job)]
        filtered_out_count = len(ranked) - len(filtered_ranked)

    # Deduplicate cross-platform by URL fallback to title+company
    deduped: List[Dict[str, object]] = []
    seen = set()
    for job in sorted(filtered_ranked, key=lambda x: x.get("match_score", 0), reverse=True):
        key = _clean_term(_best_job_url(job))
        if not key:
            key = f"{_clean_term(str(job.get('title', '')))}::{_clean_term(str(job.get('company', '')))}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    # Daily freshness: avoid repeating already-seen top jobs in today's top set
    today = datetime.utcnow().date().isoformat()
    seen_today = await db.user_job_views.find({"user_id": current_user["_id"], "viewed_date": today}, limit=1000)
    seen_keys = {str((row.get("job_key") or "")).strip() for row in seen_today if row.get("job_key")}
    fresh = []
    fallback = []
    for job in deduped:
        k = _clean_term(_best_job_url(job))
        if not k:
            k = f"{_clean_term(str(job.get('title', '')))}::{_clean_term(str(job.get('company', '')))}"
        if k in seen_keys:
            fallback.append(job)
        else:
            fresh.append((k, job))

    top_n = 10
    top_jobs = [item[1] for item in fresh[:top_n]]
    if len(top_jobs) < top_n:
        top_jobs.extend(fallback[: top_n - len(top_jobs)])

    # Prefer source diversity in top set when possible
    diversified: List[Dict[str, object]] = []
    used_platforms = set()
    for job in top_jobs:
        platform = str(job.get("platform") or "").lower()
        if platform and platform not in used_platforms:
            diversified.append(job)
            used_platforms.add(platform)
    if len(diversified) < top_n:
        for job in top_jobs:
            if job in diversified:
                continue
            diversified.append(job)
            if len(diversified) >= top_n:
                break
    top_jobs = diversified[:top_n]

    # Mark surfaced top jobs as seen for today
    for job in top_jobs:
        k = _clean_term(_best_job_url(job))
        if not k:
            k = f"{_clean_term(str(job.get('title', '')))}::{_clean_term(str(job.get('company', '')))}"
        if not k:
            continue
        view_id = str(uuid.uuid4())
        try:
            await db.user_job_views.insert_one(
                {
                    "_id": view_id,
                    "user_id": current_user["_id"],
                    "job_key": k,
                    "viewed_date": today,
                    "created_at": datetime.utcnow().isoformat(),
                }
            )
        except Exception:
            pass

    return {
        "message": "Auto search completed",
        "search_terms_used": terms,
        "location": payload.location,
        "search_requests_planned": len(search_plan),
        "max_concurrency_used": max_concurrency,
        "total_candidates": len(ranked),
        "work_auth_mode": payload.work_auth_mode,
        "work_auth_filtered_out": filtered_out_count,
        "deduped_count": len(deduped),
        "top_jobs_count": len(top_jobs),
        "failures": failures[:20],
        "jobs": top_jobs,
    }
