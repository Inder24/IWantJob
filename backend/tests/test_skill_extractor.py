from app.services.skill_extractor import SkillExtractionService


def test_extract_skills_happy_path_without_nlp():
    svc = SkillExtractionService()
    svc.nlp = None
    text = "Python Java Spring Boot AWS leadership communication"
    out = svc.extract_skills(text)
    assert "python" in out["tech_skills"]
    assert "java" in out["tech_skills"]
    assert "spring boot" in out["tech_skills"]
    assert "aws" in out["tech_skills"]
    assert "leadership" in out["soft_skills"]
    assert "communication" in out["soft_skills"]


def test_extract_companies_sad_path_no_nlp():
    svc = SkillExtractionService()
    svc.nlp = None
    companies = svc.extract_companies("Worked at OpenAI and GitHub")
    assert companies == []


def test_extract_companies_filters_common_false_positives():
    svc = SkillExtractionService()
    # Force deterministic behavior by bypassing NLP path when unavailable
    if svc.nlp is None:
        assert svc.extract_companies("AWS API LangChain") == []
        return
    text = "Work Experience at Oversea Chinese Banking Corporation and Oracle India Private Limited. Technology used: AWS API LangChain"
    companies = svc.extract_companies(text)
    joined = " | ".join(companies).lower()
    assert "aws" not in joined
    assert "api" not in joined


def test_extract_companies_prefers_date_line_employers():
    svc = SkillExtractionService()
    text = (
        "Work Experience "
        "Mar 2025 - Jul 2025: Agency for Science, Technology Research (ASTAR), Singapore "
        "Oct 2023 - Jun 2024: Oversea Chinese Banking Corporation, Singapore "
        "Dec 2021 - Sep 2023: Oracle India Private Limited, Hyderabad, India "
        "Technology used: AWS API LangChain"
    )
    companies = svc.extract_companies(text)
    joined = " | ".join(companies).lower()
    assert "agency for science" in joined
    assert "oversea chinese banking corporation" in joined
    assert "oracle india private limited" in joined
    assert "aws" not in joined


def test_extract_skills_avoids_noisy_freeform_phrases():
    svc = SkillExtractionService()
    text = (
        "This reduced development effort significantly. "
        "Partnered with product,engineering and external partners. "
        "Built services with Python, Kafka, Docker, Kubernetes."
    )
    out = svc.extract_skills(text)
    joined = " | ".join(out["tech_skills"]).lower()
    assert "this reduced development effort" not in joined
    assert "product,engineering and external partners" not in joined
    assert "python" in out["tech_skills"]
