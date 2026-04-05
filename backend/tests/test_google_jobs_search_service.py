import pytest

from app.services.google_jobs_search import GoogleJobsSearchService


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_google_jobs_service_sad_path_without_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    svc = GoogleJobsSearchService()
    with pytest.raises(RuntimeError):
        svc.search_jobs("software engineer")


def test_google_jobs_service_normalizes(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "x")
    svc = GoogleJobsSearchService()
    payload = {
        "jobs_results": [
            {
                "job_id": "abc-123",
                "title": "Software Engineer",
                "company_name": "Acme",
                "location": "Singapore",
                "description": "Build backend systems",
                "apply_options": [{"title": "Company Site", "link": "https://acme.com/jobs/abc-123"}],
                "detected_extensions": {"posted_at": "3 days ago"},
            }
        ]
    }
    monkeypatch.setattr("app.services.google_jobs_search.requests.get", lambda *args, **kwargs: _Resp(payload))
    out = svc.search_jobs("software engineer", "Singapore", 0)
    assert len(out) == 1
    assert out[0]["platform"] == "google_jobs"
    assert out[0]["job_id"] == "abc-123"
    assert out[0]["detail_url"] == "https://acme.com/jobs/abc-123"
