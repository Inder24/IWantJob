from app.services.linkedin_search import LinkedInSearchService


class _Resp400:
    status_code = 400

    def raise_for_status(self):
        raise RuntimeError("should not raise for 400 handling path")


def test_linkedin_service_returns_empty_on_400(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "x")
    svc = LinkedInSearchService()
    monkeypatch.setattr("app.services.linkedin_search.requests.get", lambda *args, **kwargs: _Resp400())
    out = svc.search_jobs("software engineer", "Singapore", 0)
    assert out == []
