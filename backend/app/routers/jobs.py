"""
Jobs router for LinkedIn search and persistence.
"""
from datetime import datetime
import uuid
from typing import List

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


def _normalize_job_url(url: str) -> str:
    return (url or "").strip()


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
