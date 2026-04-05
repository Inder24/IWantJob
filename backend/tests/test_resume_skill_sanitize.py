from app.routers.resume import _sanitize_skills


def test_sanitize_skills_removes_brackets_and_noise():
    skills = ["[Python]", "  AWS  ", '"Kubernetes"', "java", "", "  "]
    out = _sanitize_skills(skills)
    assert "python" in out
    assert "aws" in out
    assert "kubernetes" in out
    assert "java" in out
    assert all("[" not in s and "]" not in s for s in out)
