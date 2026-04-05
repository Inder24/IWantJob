from app.services.pdf_parser import PDFParsingService


def test_extract_contact_info_happy_path():
    parser = PDFParsingService()
    text = "Jane Doe jane@example.com +1 (555) 123-4567 Austin, TX"
    contact = parser.extract_contact_info(text)
    assert contact["email"] == "jane@example.com"
    assert contact["phone"] is not None
    assert contact["location"] == "Austin, TX"


def test_parse_pdf_sad_path_invalid_bytes():
    parser = PDFParsingService()
    result = parser.parse_pdf(b"not a real pdf")
    assert result["success"] is False
    assert result["raw_text"] == ""
    assert result["error"]


def test_extract_contact_info_avoids_langchain_mcp_false_location():
    parser = PDFParsingService()
    text = "SIMRAN ARORA Singapore simran@u.nus.edu ... LangChain, MCP ..."
    contact = parser.extract_contact_info(text)
    assert contact["location"] != "Chain, MC"
    assert contact["location"] in ("Singapore", "ARORA, Singapore", "Simran, Singapore")
