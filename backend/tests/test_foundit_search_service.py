import pytest

from app.services.foundit_search import FounditSearchService


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_foundit_service_sad_path_without_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    svc = FounditSearchService()
    with pytest.raises(RuntimeError):
        svc.search_jobs("backend engineer")


def test_foundit_service_normalizes(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "x")
    svc = FounditSearchService()
    payload = {
        "organic_results": [
            {
                "position": 1,
                "title": "Backend Engineer | Contoso",
                "link": "https://foundit.sg/job/backend-123",
                "snippet": "Great role in Singapore.",
            }
        ]
    }
    monkeypatch.setattr("app.services.foundit_search.requests.get", lambda *args, **kwargs: _Resp(payload))
    out = svc.search_jobs("backend engineer", "Singapore", 0)
    assert len(out) == 1
    assert out[0]["platform"] == "foundit"
    assert out[0]["company"] == "Contoso"
    assert out[0]["detail_url"] == "https://foundit.sg/job/backend-123"
