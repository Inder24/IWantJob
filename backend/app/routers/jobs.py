"""
Jobs router for multi-source search and persistence.
"""
from datetime import datetime
import uuid
from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import requests

from app.database import get_database
from app.routers.auth import get_current_user
from app.services.linkedin_search import linkedin_search_service
from app.services.indeed_search import indeed_search_service
from app.services.foundit_search import foundit_search_service


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


def _normalize_job_url(url: str) -> str:
    return (url or "").strip()


def _clean_term(value: str) -> str:
    return " ".join((value or "").lower().strip().split())


def _build_query_terms(resume: dict, max_terms: int) -> List[str]:
    parsed = (resume or {}).get("parsed_data") or {}
    search_terms = resume.get("search_terms") or []
    skills = parsed.get("skills") or []
    experience = parsed.get("experience") or []

    titles: List[str] = []
    for exp in experience:
        title = (exp or {}).get("title", "").strip()
        if title:
            titles.append(title)

    candidates: List[str] = []
    candidates.extend(search_terms[:8])
    candidates.extend(titles[:4])
    for skill in skills[:8]:
        s = str(skill).strip()
        if not s:
            continue
        candidates.append(f"{s} developer")
        candidates.append(f"{s} engineer")
    candidates.extend(["software engineer", "backend engineer"])

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


async def _upsert_jobs(db, platform: str, jobs: List[dict], query: str, location: str):
    inserted = 0
    updated = 0
    saved_ids: List[str] = []

    for job in jobs:
        existing = await db.jobs.find_one({"platform": platform, "job_id": job["job_id"]})
        if not existing and job.get("url"):
            existing = await db.jobs.find_one({"platform": platform, "url": _normalize_job_url(job.get("url", ""))})

        if existing:
            await db.jobs.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "title": job["title"],
                        "company": job["company"],
                        "location": job.get("location", ""),
                        "description": job.get("description", ""),
                        "url": _normalize_job_url(job.get("url", "")),
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
                "url": _normalize_job_url(job.get("url", "")),
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

    for term in terms:
        for source_name, source_fn in (
            ("linkedin", linkedin_search_service.search_jobs),
            ("indeed", indeed_search_service.search_jobs),
            ("foundit", foundit_search_service.search_jobs),
        ):
            try:
                jobs = source_fn(term, payload.location, payload.per_source_page)
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

    # Deduplicate cross-platform by URL fallback to title+company
    deduped: List[Dict[str, object]] = []
    seen = set()
    for job in sorted(ranked, key=lambda x: x.get("match_score", 0), reverse=True):
        key = _clean_term(str(job.get("url") or ""))
        if not key:
            key = f"{_clean_term(str(job.get('title', '')))}::{_clean_term(str(job.get('company', '')))}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)

    return {
        "message": "Auto search completed",
        "search_terms_used": terms,
        "location": payload.location,
        "total_candidates": len(ranked),
        "deduped_count": len(deduped),
        "failures": failures[:20],
        "jobs": deduped[:100],
    }
