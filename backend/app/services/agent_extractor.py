"""
Optional Gemini-based resume extraction helpers.
"""
import json
import os
import re
import time
from typing import Dict, Any, List

import requests


class GeminiResumeExtractor:
    def __init__(self):
        self.enabled = os.getenv("ENABLE_AGENT_EXTRACTION", "false").lower() == "true"
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.max_retries = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
        self.base_backoff_seconds = float(os.getenv("GEMINI_BACKOFF_SECONDS", "1.0"))

    def is_enabled(self) -> bool:
        return self.enabled and bool(self.api_key)

    async def extract_resume_intelligence(self, resume_text: str) -> Dict[str, Any]:
        if not self.is_enabled():
            return {
                "companies": [],
                "location": None,
                "skills": [],
                "resume_score": None,
                "improvement_suggestions": [],
            }

        prompt = (
            "Extract structured resume intelligence from this resume text.\n"
            "Return ONLY valid JSON with this exact schema:\n"
            '{"companies": ["..."], "location": "...", "skills": ["..."], "resume_score": 0, '
            '"improvement_suggestions": ["..."] }\n'
            "Rules:\n"
            "- companies: only employer names from work experience timeline.\n"
            "- exclude technologies/tools/skills (AWS, API, Kafka, Docker, etc).\n"
            "- location: best current candidate location if present.\n"
            "- skills: include practical technical and role-relevant skills for job search.\n"
            "- resume_score: integer 0-100 based on clarity, impact, ATS-friendliness, and completeness.\n"
            "- improvement_suggestions: 3-8 concise actionable bullets.\n"
            "- If unknown, use null for location and [] for companies.\n\n"
            f"RESUME:\n{resume_text[:12000]}"
        )

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }

        data = self._post_with_backoff(url, payload)

        text = self._response_text(data)
        parsed = self._parse_json_text(text)
        companies = parsed.get("companies", [])
        location = parsed.get("location")
        skills = parsed.get("skills", [])
        score = parsed.get("resume_score")
        suggestions = parsed.get("improvement_suggestions", [])

        if not isinstance(companies, list):
            companies = []
        companies = [c.strip() for c in companies if isinstance(c, str) and c.strip()]
        location = location.strip() if isinstance(location, str) and location.strip() else None

        if not isinstance(skills, list):
            skills = []
        skills = [s.strip().lower() for s in skills if isinstance(s, str) and s.strip()]

        if not isinstance(suggestions, list):
            suggestions = []
        suggestions = [s.strip() for s in suggestions if isinstance(s, str) and s.strip()]

        if not isinstance(score, int):
            score = None
        elif score < 0:
            score = 0
        elif score > 100:
            score = 100

        return {
            "companies": companies[:10],
            "location": location,
            "skills": skills[:50],
            "resume_score": score,
            "improvement_suggestions": suggestions[:8],
        }

    async def extract_companies_and_location(self, resume_text: str) -> Dict[str, Any]:
        intelligence = await self.extract_resume_intelligence(resume_text)
        return {
            "companies": intelligence.get("companies", []),
            "location": intelligence.get("location"),
        }

    def _post_with_backoff(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            response = requests.post(url, json=payload, timeout=25)
            if response.status_code < 400:
                return response.json()
            # Retry only on rate limit/transient server issues
            if response.status_code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                sleep_seconds = self.base_backoff_seconds * (2 ** attempt)
                time.sleep(sleep_seconds)
                continue
            response.raise_for_status()
        return {}

    def _response_text(self, data: Dict[str, Any]) -> str:
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = (((candidates[0] or {}).get("content") or {}).get("parts") or [])
        if not parts:
            return ""
        return parts[0].get("text", "") or ""

    def _parse_json_text(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        # Try raw JSON first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try fenced JSON or embedded JSON
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


agent_extractor = GeminiResumeExtractor()
