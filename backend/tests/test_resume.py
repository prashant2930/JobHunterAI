import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.resume_parser import DocumentExtractor
from app.services.llm_client import FakeLLMClient, set_llm_client, get_llm_client
from app.models.candidate import CandidateProfileSchema, PersonalInfoSchema, SkillsSchema

# ==========================================
# 1. Document Extraction Unit Tests
# ==========================================

def test_pdf_extraction_mock():
    """Verify that PDF extractor extracts text correctly using pypdf."""
    with patch("app.services.resume_parser.PdfReader") as mock_reader:
        # Mock pypdf reader hierarchy
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Senior Python Engineer\nSkills: FastAPI, SQLite"
        mock_pdf.pages = [mock_page]
        mock_reader.return_value = mock_pdf
        
        extracted_text = DocumentExtractor.extract("resume.pdf", b"dummy_pdf_bytes")
        assert "Senior Python Engineer" in extracted_text
        assert "FastAPI" in extracted_text

def test_docx_extraction_mock():
    """Verify that DOCX extractor extracts text correctly using docx2txt."""
    with patch("app.services.resume_parser.docx2txt.process") as mock_process:
        mock_process.return_value = "Staff React Developer\nSkills: TypeScript, Tailwind"
        
        extracted_text = DocumentExtractor.extract("resume.docx", b"dummy_docx_bytes")
        assert "Staff React Developer" in extracted_text
        assert "Tailwind" in extracted_text
        mock_process.assert_called_once()

def test_unsupported_file_type():
    """Verify that uploading an unsupported format throws a ValueError."""
    with pytest.raises(ValueError) as exc:
        DocumentExtractor.extract("resume.txt", b"plain_text_bytes")
    assert "Unsupported file type" in str(exc.value)

def test_empty_document_validation():
    """Verify that empty documents are detected and throw ValueError."""
    with patch("app.services.resume_parser.PdfReader") as mock_reader:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "   \n   "
        mock_pdf.pages = [mock_page]
        mock_reader.return_value = mock_pdf
        
        with pytest.raises(ValueError) as exc:
            DocumentExtractor.extract("resume.pdf", b"dummy_pdf_bytes")
        assert "empty or unreadable" in str(exc.value)


# ==========================================
# 2. Schema and LLM Client Unit Tests
# ==========================================

def test_fake_llm_client_returns_valid_schema():
    """Verify that FakeLLMClient returns a schema structure with empty preferences."""
    client = FakeLLMClient()
    profile = client.parse_resume("sample text")
    
    assert isinstance(profile, CandidateProfileSchema)
    assert profile.personal_info.name == "John Doe"
    # Preferences must be empty or null initially
    assert len(profile.preferences.preferred_roles) == 0
    assert profile.preferences.remote_preference is None
    assert profile.profile_source == "extracted"
    assert profile.preferences_source == "none"


# ==========================================
# 3. API Routing and Integration Tests
# ==========================================

def test_api_upload_resume_endpoint():
    """Verify resume upload API route maps to FakeLLMClient and returns Pydantic validation."""
    # 1. Inject the FakeLLMClient in tests to prevent real Gemini hits
    set_llm_client(FakeLLMClient())
    
    client = TestClient(app)
    
    # 2. Patch DocumentExtractor so it doesn't need real PDF bytes
    with patch("app.services.resume_parser.DocumentExtractor.extract") as mock_extract:
        mock_extract.return_value = "Fictional Candidate Resume Text"
        
        response = client.post(
            "/api/profile/resume",
            files={"file": ("resume.pdf", b"mock_pdf_binary_content", "application/pdf")}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify schema mapping and outputs
        assert data["personal_info"]["name"] == "John Doe"
        assert len(data["skills"]["programming_languages"]) > 0
        assert data["profile_source"] == "extracted"
        assert data["preferences_source"] == "none"
        
        # Assert preferences are completely empty in the endpoint response
        assert len(data["preferences"]["preferred_locations"]) == 0
        assert data["preferences"]["remote_preference"] is None
        
        mock_extract.assert_called_once()

def test_api_upload_invalid_file_type():
    """Verify that uploading an unsupported format returns 400 Bad Request."""
    client = TestClient(app)
    response = client.post(
        "/api/profile/resume",
        files={"file": ("resume.txt", b"plain_text_bytes", "text/plain")}
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
