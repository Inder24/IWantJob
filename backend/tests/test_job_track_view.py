from app.routers.jobs import _job_view_key


def test_job_view_key_uses_title_company_when_url_missing():
    key = _job_view_key("", "Software Engineer", "Acme")
    assert key == "software engineer::acme"
