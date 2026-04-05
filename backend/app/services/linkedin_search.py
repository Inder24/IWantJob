"""
LinkedIn job search service.
Uses SerpAPI as an integration backend when configured.
"""
from datetime import datetime
import os
from typing import Any, Dict, List

import requests


class LinkedInSearchService:
    def __init__(self):
        self.serpapi_key = os.getenv("SERPAPI_API_KEY", "").strip()
        self.timeout = int(os.getenv("LINKEDIN_HTTP_TIMEOUT_SECONDS", "20"))
        self.max_results = int(os.getenv("LINKEDIN_MAX_RESULTS", "20"))

    def is_enabled(self) -> bool:
        return bool(self.serpapi_key)

    def search_jobs(self, query: str, location: str = "", page: int = 0) -> List[Dict[str, Any]]:
        """Search LinkedIn jobs and normalize results."""
        if not self.is_enabled():
            raise RuntimeError("LinkedIn integration is not configured. Set SERPAPI_API_KEY.")

        params = {
            "engine": "linkedin_jobs",
            "api_key": self.serpapi_key,
            "keywords": query,
            "start": max(page, 0) * max(self.max_results, 1),
        }
        if location:
            params["location"] = location

        response = requests.get("https://serpapi.com/search.json", params=params, timeout=self.timeout)
        if response.status_code == 400:
            # If LinkedIn engine is unavailable for this key/plan, degrade gracefully.
            return []
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])

        normalized: List[Dict[str, Any]] = []
        now = datetime.utcnow().isoformat()
        for item in jobs[: self.max_results]:
            title = (item.get("title") or "").strip()
            company = (item.get("company_name") or item.get("company") or "").strip()
            if not title or not company:
                continue
            raw_job_id = str(item.get("job_id") or item.get("id") or "").strip()
            link = (item.get("link") or item.get("job_url") or "").strip()
            job_id = raw_job_id or link or f"{title}:{company}:{item.get('location', '')}"
            normalized.append(
                {
                    "platform": "linkedin",
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": (item.get("location") or "").strip(),
                    "description": (item.get("description") or "").strip(),
                    "url": link,
                    "posted_date": (item.get("detected_extensions", {}) or {}).get("posted_at"),
                    "scraped_at": now,
                }
            )
        return normalized


linkedin_search_service = LinkedInSearchService()
