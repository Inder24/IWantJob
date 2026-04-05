from datetime import datetime
import pytest
from pydantic import ValidationError

from app.models.schemas import UserCreate, UserLogin, Resume, ParsedData
from app.routers.jobs import AutoSearchRequest


def test_usercreate_happy_path():
    u = UserCreate(username="inder", email="inder@example.com", password="secret123")
    assert u.username == "inder"


def test_usercreate_sad_path_short_password():
    with pytest.raises(ValidationError):
        UserCreate(username="inder", email="inder@example.com", password="123")


def test_resume_happy_path():
    r = Resume(
        _id="r1",
        user_id="u1",
        filename="resume.pdf",
        upload_date=datetime.utcnow(),
        parsed_data=ParsedData(raw_text="x"),
        search_terms=["python developer"],
        updated_at=datetime.utcnow(),
    )
    assert r.user_id == "u1"
    assert r.parsed_data.raw_text == "x"


def test_resume_sad_path_missing_filename():
    with pytest.raises(ValidationError):
        Resume(
            _id="r1",
            user_id="u1",
            upload_date=datetime.utcnow(),
            parsed_data=ParsedData(raw_text="x"),
            search_terms=[],
            updated_at=datetime.utcnow(),
        )


def test_auto_search_request_defaults_work_auth_mode():
    req = AutoSearchRequest()
    assert req.work_auth_mode == "singapore_pr"


def test_auto_search_request_rejects_invalid_work_auth_mode():
    with pytest.raises(ValidationError):
        AutoSearchRequest(work_auth_mode="invalid_mode")
