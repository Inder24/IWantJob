import pytest

from app.services.indeed_search import IndeedSearchService


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_indeed_service_sad_path_without_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    svc = IndeedSearchService()
    with pytest.raises(RuntimeError):
        svc.search_jobs("python developer")


def test_indeed_service_normalizes(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "x")
    svc = IndeedSearchService()
    payload = {
        "organic_results": [
            {
                "position": 1,
                "title": "Python Developer - Acme",
                "link": "https://sg.indeed.com/viewjob?jk=abc",
                "snippet": "Singapore role at Acme.",
            }
        ]
    }
    monkeypatch.setattr("app.services.indeed_search.requests.get", lambda *args, **kwargs: _Resp(payload))
    out = svc.search_jobs("python developer", "Singapore", 0)
    assert len(out) == 1
    assert out[0]["platform"] == "indeed"
    assert out[0]["company"] == "Acme"


def test_indeed_service_filters_listing_pages(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "x")
    svc = IndeedSearchService()
    payload = {
        "organic_results": [
            {
                "position": 1,
                "title": "100+ Software Developer Jobs, Employment April 3, 2026",
                "link": "https://sg.indeed.com/jobs?q=software+developer",
                "snippet": "Listing page",
            }
        ]
    }
    monkeypatch.setattr("app.services.indeed_search.requests.get", lambda *args, **kwargs: _Resp(payload))
    out = svc.search_jobs("software developer", "Singapore", 0)
    assert out == []
