import pytest

from app.services.linkedin_search import LinkedInSearchService


class _Resp:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_linkedin_search_service_sad_path_without_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    svc = LinkedInSearchService()
    with pytest.raises(RuntimeError):
        svc.search_jobs("python developer")


def test_linkedin_search_service_normalizes_results(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "x")
    monkeypatch.setenv("LINKEDIN_MAX_RESULTS", "2")
    svc = LinkedInSearchService()

    payload = {
        "jobs": [
            {
                "job_id": "123",
                "title": "Backend Engineer",
                "company_name": "Acme",
                "location": "Singapore",
                "description": "Build APIs",
                "link": "https://www.linkedin.com/jobs/view/123",
                "detected_extensions": {"posted_at": "2 days ago"},
            }
        ]
    }

    monkeypatch.setattr("app.services.linkedin_search.requests.get", lambda *args, **kwargs: _Resp(payload))
    out = svc.search_jobs("backend engineer", "Singapore", 0)
    assert len(out) == 1
    assert out[0]["platform"] == "linkedin"
    assert out[0]["job_id"] == "123"
    assert out[0]["title"] == "Backend Engineer"
    assert out[0]["company"] == "Acme"
