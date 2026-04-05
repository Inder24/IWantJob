from app.routers.jobs import _build_query_terms, _score_job


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


def test_score_job_happy_path():
    job = {
        "title": "Python Backend Engineer",
        "description": "FastAPI AWS microservices",
        "location": "Singapore",
    }
    score = _score_job(job, ["python developer", "backend engineer"], ["python", "fastapi", "aws"], "Singapore")
    assert score > 30
