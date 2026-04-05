"""
Foundit (Monster Singapore) job search service via SerpAPI Google results.
"""
from datetime import datetime
import os
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

import requests


class FounditSearchService:
    def __init__(self):
        self.serpapi_key = os.getenv("SERPAPI_API_KEY", "").strip()
        self.timeout = int(os.getenv("FOUNDIT_HTTP_TIMEOUT_SECONDS", "20"))
        self.max_results = int(os.getenv("FOUNDIT_MAX_RESULTS", "20"))
        self.google_domain = os.getenv("SERPAPI_GOOGLE_DOMAIN", "google.com")
        self.google_gl = os.getenv("SERPAPI_GOOGLE_GL", "sg")
        self.google_hl = os.getenv("SERPAPI_GOOGLE_HL", "en")

    def is_enabled(self) -> bool:
        return bool(self.serpapi_key)

    def _extract_company(self, title: str, snippet: str, link: str) -> str:
        for sep in (" - ", " | ", " @ "):
            parts = [p.strip() for p in title.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts[1]
        if "company" in snippet.lower():
            lower = snippet.lower()
            idx = lower.find("company")
            tail = snippet[idx + len("company") :].strip(" :.-")
            if tail:
                return tail.split(".")[0].split(",")[0].strip()[:120]
        host = urlparse(link).netloc.replace("www.", "")
        return host or "Unknown"

    def _extract_location(self, title: str, snippet: str) -> str:
        text = f"{title} {snippet}".lower()
        if "singapore" in text:
            return "Singapore"
        return ""

    def search_jobs(self, query: str, location: str = "", page: int = 0) -> List[Dict[str, Any]]:
        if not self.is_enabled():
            raise RuntimeError("Foundit integration is not configured. Set SERPAPI_API_KEY.")

        offset = max(page, 0) * max(self.max_results, 1)
        q = f'site:foundit.sg/jobs "{query}"'
        if location:
            q += f' "{location}"'

        params = {
            "engine": "google",
            "api_key": self.serpapi_key,
            "q": q,
            "num": self.max_results,
            "start": offset,
            "google_domain": self.google_domain,
            "gl": self.google_gl,
            "hl": self.google_hl,
        }
        response = requests.get("https://serpapi.com/search.json", params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        normalized: List[Dict[str, Any]] = []
        now = datetime.utcnow().isoformat()
        for item in (data.get("organic_results") or [])[: self.max_results]:
            title = (item.get("title") or "").strip()
            link = unquote((item.get("link") or "").strip())
            snippet = (item.get("snippet") or "").strip()
            if not title or not link:
                continue
            job_id = str(item.get("position") or link)
            normalized.append(
                {
                    "platform": "foundit",
                    "job_id": job_id,
                    "title": title[:200],
                    "company": self._extract_company(title, snippet, link),
                    "location": self._extract_location(title, snippet),
                    "description": snippet,
                    "url": link,
                    "posted_date": None,
                    "scraped_at": now,
                }
            )
        return normalized


foundit_search_service = FounditSearchService()
