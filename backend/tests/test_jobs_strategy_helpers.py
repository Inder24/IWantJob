from app.routers.jobs import (
    _best_job_url,
    _build_query_terms,
    _is_contract_role,
    _is_work_visa_ineligible,
    _job_view_key,
    _score_job,
)


def test_build_query_terms_happy_path():
    resume = {
        "search_terms": ["python developer", "backend engineer"],
        "parsed_data": {
            "skills": ["python", "fastapi", "aws"],
            "role_terms": ["software engineer", "backend engineer"],
            "experience": [{"title": "Software Engineer"}],
        },
    }
    terms = _build_query_terms(resume, 6)
    assert len(terms) > 0
    lowered = [t.lower() for t in terms]
    assert "software engineer" in lowered or "backend engineer" in lowered


def test_build_query_terms_adds_senior_lead_variants():
    resume = {
        "search_terms": ["java developer"],
        "parsed_data": {"role_terms": ["software engineer"], "skills": [], "experience": []},
    }
    terms = _build_query_terms(resume, 12)
    lowered = [t.lower() for t in terms]
    assert any(t.startswith("senior ") for t in lowered)
    assert any(t.startswith("lead ") for t in lowered)


def test_score_job_happy_path():
    job = {
        "title": "Python Backend Engineer",
        "description": "FastAPI AWS microservices",
        "location": "Singapore",
    }
    score = _score_job(job, ["python developer", "backend engineer"], ["python", "fastapi", "aws"], "Singapore")
    assert score > 30


def test_work_visa_filter_detects_ineligible_phrase():
    job = {
        "title": "Software Engineer",
        "description": "Singapore PR only role. Work pass not provided.",
    }
    assert _is_work_visa_ineligible(job) is True


def test_work_visa_filter_allows_generic_job():
    job = {
        "title": "Backend Engineer",
        "description": "Build APIs with Python and FastAPI in Singapore.",
    }
    assert _is_work_visa_ineligible(job) is False


def test_best_job_url_prefers_detail_url():
    job = {"url": "https://example.com/generic", "detail_url": "https://example.com/detail"}
    assert _best_job_url(job) == "https://example.com/detail"


def test_contract_role_filter_detects_contract():
    job = {"title": "Software Engineer (Contract)", "description": "12 month renewable contract role"}
    assert _is_contract_role(job) is True


def test_contract_role_filter_allows_full_time():
    job = {"title": "Software Engineer", "description": "Permanent full-time role in Singapore"}
    assert _is_contract_role(job) is False


def test_job_view_key_prefers_url():
    assert _job_view_key("https://example.com/job/1", "Engineer", "Acme") == "https://example.com/job/1"
