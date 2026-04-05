"""
Google Jobs search service via SerpAPI Google Jobs engine.
"""
from datetime import datetime
import os
from typing import Any, Dict, List

import requests


class GoogleJobsSearchService:
    def __init__(self):
        self.serpapi_key = os.getenv("SERPAPI_API_KEY", "").strip()
        self.timeout = int(os.getenv("GOOGLE_JOBS_HTTP_TIMEOUT_SECONDS", "20"))
        self.max_results = int(os.getenv("GOOGLE_JOBS_MAX_RESULTS", "20"))

    def is_enabled(self) -> bool:
        return bool(self.serpapi_key)

    @staticmethod
    def _best_job_link(item: Dict[str, Any]) -> str:
        apply_options = item.get("apply_options") or []
        for option in apply_options:
            link = (option or {}).get("link")
            if isinstance(link, str) and link.strip():
                return link.strip()

        related_links = item.get("related_links") or []
        for option in related_links:
            link = (option or {}).get("link")
            if isinstance(link, str) and link.strip():
                return link.strip()

        share_link = item.get("share_link")
        if isinstance(share_link, str) and share_link.strip():
            return share_link.strip()

        return ""

    def search_jobs(self, query: str, location: str = "", page: int = 0) -> List[Dict[str, Any]]:
        if not self.is_enabled():
            raise RuntimeError("Google Jobs integration is not configured. Set SERPAPI_API_KEY.")

        offset = max(page, 0) * max(self.max_results, 1)
        params = {
            "engine": "google_jobs",
            "api_key": self.serpapi_key,
            "q": query,
            "start": offset,
        }
        if location:
            params["location"] = location

        response = requests.get("https://serpapi.com/search.json", params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        normalized: List[Dict[str, Any]] = []
        now = datetime.utcnow().isoformat()
        for item in (data.get("jobs_results") or [])[: self.max_results]:
            title = (item.get("title") or "").strip()
            company = (item.get("company_name") or item.get("company") or "").strip()
            if not title or not company:
                continue

            link = self._best_job_link(item)
            job_id = str(item.get("job_id") or link or f"{title}:{company}:{item.get('location', '')}")
            normalized.append(
                {
                    "platform": "google_jobs",
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": (item.get("location") or "").strip(),
                    "description": (item.get("description") or "").strip(),
                    "url": link,
                    "detail_url": link,
                    "posted_date": (item.get("detected_extensions") or {}).get("posted_at"),
                    "scraped_at": now,
                }
            )
        return normalized


google_jobs_search_service = GoogleJobsSearchService()
