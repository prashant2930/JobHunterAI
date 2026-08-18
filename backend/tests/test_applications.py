import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
import asyncio

from app.main import app
from app.database import engine, init_db
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.application import Application, ApplicationFormField
from app.services.llm_client import set_llm_client, FakeLLMClient
from app.services.application_analyzer import ApplicationAnalyzerService

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()
    set_llm_client(FakeLLMClient())

@pytest.fixture
def test_data():
    with Session(engine) as session:
        profile = session.exec(select(CandidateProfile)).first()
        if not profile:
            profile = CandidateProfile(
                name="Alice Smith",
                email="alice@example.com",
                phone="555-0199",
                location="San Francisco, CA",
                skills_programming_languages=["Python", "TypeScript"],
                links=["https://linkedin.com/in/alicesmith", "https://github.com/alicesmith"]
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)

        job = Job(
            title="Backend Engineer",
            normalized_title="backend engineer",
            company="Acme Corp",
            normalized_company="acme corp",
            location="San Francisco, CA",
            normalized_location="san francisco ca",
            source="test",
            source_job_id="test-123",
            description="We are looking for a Python backend engineer to build scalable services.",
            application_url="https://example.com/jobs/123/apply"
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        profile_id = profile.id
        job_id = job.job_id

    return profile_id, job_id


def test_application_analysis_and_profile_field_mapping(test_data):
    profile_id, job_id = test_data

    # Call analyze API endpoint
    response = client.post(
        "/api/applications/analyze",
        json={"job_id": job_id}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["job_id"] == job_id
    assert data["candidate_profile_id"] == str(profile_id)
    assert data["status"] == "READY_FOR_REVIEW"
    assert len(data["fields"]) > 0

    field_map = {f["field_name"]: f for f in data["fields"]}

    # Verify deterministic profile mapping
    assert field_map["first_name"]["current_value"] == "Alice"
    assert field_map["first_name"]["source"] == "candidate_profile"
    assert field_map["first_name"]["confidence"] == 1.0
    assert field_map["first_name"]["requires_review"] is False

    assert field_map["last_name"]["current_value"] == "Smith"
    assert field_map["last_name"]["source"] == "candidate_profile"

    assert field_map["email"]["current_value"] == "alice@example.com"
    assert field_map["email"]["source"] == "candidate_profile"

    assert field_map["phone"]["current_value"] == "555-0199"

    assert "linkedin.com/in/alicesmith" in field_map["linkedin_url"]["current_value"]


def test_ambiguous_question_requires_review(test_data):
    profile_id, job_id = test_data

    html_form = """
    <form>
        <label for="why_work_here">Why do you want to work at Acme Corp?</label>
        <textarea id="why_work_here" name="why_work_here"></textarea>

        <label for="work_auth">Are you legally authorized to work in the US?</label>
        <select id="work_auth" name="work_auth">
            <option value="Yes">Yes</option>
            <option value="No">No</option>
        </select>
    </form>
    """

    with Session(engine) as session:
        profile = session.get(CandidateProfile, profile_id)
        job = session.get(Job, job_id)

        app_model = asyncio.run(
            ApplicationAnalyzerService.analyze_job_application(
                job=job,
                profile=profile,
                session=session,
                html_content=html_form
            )
        )

        assert app_model.id is not None
        fields = {f.field_name: f for f in app_model.fields}

        # Ambiguous question should require review
        assert fields["why_work_here"].requires_review is True

        # Factual unknown question should also require review and not invent facts
        assert fields["work_auth"].requires_review is True
        assert fields["work_auth"].source == "unknown"


def test_application_approval_and_non_submission(test_data):
    profile_id, job_id = test_data

    # 1. Trigger analysis
    response = client.post(
        "/api/applications/analyze",
        json={"job_id": job_id}
    )
    assert response.status_code == 200
    app_data = response.json()
    app_id = app_data["id"]

    # 2. Approve application
    approve_response = client.post(
        f"/api/applications/{app_id}/approve",
        json={
            "field_updates": [
                {"field_id": app_data["fields"][0]["id"], "current_value": "Alice", "requires_review": False}
            ]
        }
    )
    assert approve_response.status_code == 200
    approved_data = approve_response.json()

    # Verify status changed to APPROVED
    assert approved_data["status"] == "APPROVED"

    # Verify all fields require_review is now False
    for f in approved_data["fields"]:
        assert f["requires_review"] is False

    # 3. CONFIRMATION: Status remains APPROVED and no automated external submission exists
    assert approved_data["status"] != "SUBMITTED"

    # Retrieve again via GET to verify persistent approved state
    get_res = client.get(f"/api/applications/{app_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "APPROVED"
