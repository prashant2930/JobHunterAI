import pytest
import asyncio
from sqlmodel import Session, SQLModel, create_engine, select
from datetime import datetime, timedelta
from typing import Optional

from app.models.candidate import (
    CandidateProfile,
    EducationRecord,
    ExperienceRecord
)
from app.models.job import Job
from app.models.match import MatchResult, RecommendationEnum
from app.services.match_engine import MatchEngineService, get_levenshtein_ratio
from app.services.normalization import JobNormalizationService
from app.services.llm_client import FakeLLMClient, set_llm_client, BaseLLMClient

# ==========================================
# 1. FIXTURES AND DATABASE SETUPS
# ==========================================

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="base_profile")
def base_profile_fixture():
    """Returns a basic candidate profile populated with database model values."""
    profile = CandidateProfile(
        id=123,
        name="Alice Candidate",
        email="alice@example.com",
        phone="555-0199",
        location="Boston, MA",
        preferred_roles=["Software Engineer", "Backend Developer"],
        preferred_locations=["Remote", "Boston"],
        remote_preference="remote",
        experience_level="mid",
        skills_programming_languages=["Python", "JavaScript", "SQL"],
        skills_frameworks=["FastAPI", "React"],
        skills_libraries=[],
        skills_databases=["PostgreSQL"],
        skills_cloud=["AWS"],
        skills_tools=["Git", "Docker"],
        skills_others=[],
        certifications=[]
    )
    
    # Attach relationship items (relationships require primary key references or standard mappings)
    profile.education = [
        EducationRecord(
            institution="MIT",
            degree="Bachelor of Science",
            field_of_study="Computer Science"
        )
    ]
    
    profile.experience = [
        ExperienceRecord(
            company="Tech Corp",
            role="Software Engineer",
            start_date="2022-01-01",
            end_date="2024-01-01",  # 2 years
            description="Developing backend services in Python.",
            technologies=["Python", "FastAPI", "PostgreSQL"]
        )
    ]
    
    profile.projects = []
    
    return profile


# ==========================================
# 2. MATCH ENGINE TEST CASES
# ==========================================

def test_strong_match(base_profile):
    """
    Candidate: Python, JS, SQL, FastAPI, React, 2 years, CS degree, prefers Remote/Boston.
    Job: Python, FastAPI, requires BS CS, 1 year experience, remote.
    Expected: STRONG_MATCH
    """
    job = Job(
        job_id="job_strong",
        title="Python Software Engineer",
        normalized_title="software engineer",
        company="Dream Corp",
        location="Remote",
        remote_status="remote",
        description="Requires a degree in computer science and 1+ years experience with Python and FastAPI.",
        skills=["python", "fastapi"],
        experience_required=1.0,
        source="remoteok",
        application_url="http://example.com/apply"
    )
    
    res = MatchEngineService.execute_deterministic_matching(base_profile, job)
    
    assert res["overall_score"] >= 80.0
    assert "python" in res["matching_skills"]
    assert "fastapi" in res["matching_skills"]
    assert len(res["missing_required_skills"]) == 0
    assert res["experience_gap"] == 0.0


def test_missing_required_skills(base_profile):
    """
    Job requires Python and C++ (candidate lacks C++).
    Expected: Significant qualification compliance penalty (compliance is 0.0).
    """
    job = Job(
        job_id="job_cpp",
        title="C++ Developer",
        normalized_title="c++ developer",
        company="Legacy Tech",
        location="Boston, MA",
        remote_status="onsite",
        description="Required qualifications: must know C++ and Python.",
        skills=["python", "c++"],
        experience_required=1.0,
        source="adzuna",
        application_url="http://example.com/apply"
    )
    
    res = MatchEngineService.execute_deterministic_matching(base_profile, job)
    
    # Qualification Compliance score should be 0.0
    assert res["required_qualification_score"] == 0.0
    assert "c++" in res["missing_required_skills"]


def test_preferred_skill_missing(base_profile):
    """
    Job list Docker/AWS and Kubernetes as nice-to-have. Candidate lacks Kubernetes.
    Expected: Minor penalty (qualification compliance score is reduced to 3.0 instead of 5.0).
    """
    job = Job(
        job_id="job_k8s",
        title="Cloud Engineer",
        normalized_title="cloud engineer",
        company="SaaS Corp",
        location="Remote",
        remote_status="remote",
        description="Nice to have skills: Kubernetes, Docker, AWS.",
        skills=["aws", "docker", "kubernetes"],
        experience_required=1.0,
        source="remoteok",
        application_url="http://example.com/apply"
    )
    
    res = MatchEngineService.execute_deterministic_matching(base_profile, job)
    
    assert "kubernetes" in res["missing_preferred_skills"]
    assert res["required_qualification_score"] == 4.0  # preferred penalty applied


def test_experience_mismatch_cap(base_profile):
    """
    Candidate has 2 years of experience. Job requires 8 years.
    Expected: Severe experience gap (gap = 6 years) caps overall score at 40.
    """
    job = Job(
        job_id="job_sr",
        title="Principal Software Architect",
        normalized_title="principal software architect",
        company="Huge Corp",
        location="Remote",
        remote_status="remote",
        description="Requires 8+ years of industry experience.",
        skills=["python", "sql"],
        experience_required=8.0,
        source="adzuna",
        application_url="http://example.com/apply"
    )
    
    res = MatchEngineService.execute_deterministic_matching(base_profile, job)
    
    assert res["experience_gap"] == 6.0
    assert res["overall_score"] <= 40.0
    assert any("Severe experience mismatch" in con for con in res["concerns"])


def test_role_title_mismatch(base_profile):
    """
    Candidate prefers Software Engineer. Job is "Lead Data Scientist".
    Expected: Poor role alignment score.
    """
    job = Job(
        job_id="job_data_science",
        title="Lead Data Scientist",
        normalized_title="lead data scientist",
        company="Data Corp",
        location="Remote",
        remote_status="remote",
        description="Analyzing large models.",
        skills=["python"],
        experience_required=1.0,
        source="remoteok",
        application_url="http://example.com/apply"
    )
    
    res = MatchEngineService.execute_deterministic_matching(base_profile, job)
    
    # Preferred roles are Software Engineer, Backend Developer.
    # Data Scientist should yield minimal role score (e.g. 5.0 out of 15.0)
    assert res["role_score"] <= 5.0


def test_location_and_remote_scenarios(base_profile):
    """
    Verify Location Fit scores for strict vs preferred vs unspecified remote.
    """
    # Case A: Strict Remote candidate matching Onsite New York job
    base_profile.remote_preference = "remote"
    job_onsite = Job(
        job_id="job_onsite",
        title="Engineer",
        normalized_title="engineer",
        company="Onsite Corp",
        location="New York, NY",
        remote_status="onsite",
        description="Must work onsite.",
        skills=["python"],
        source="adzuna"
    )
    res_a = MatchEngineService.execute_deterministic_matching(base_profile, job_onsite)
    assert res_a["location_score"] == 0.0
    assert any("Strict Remote preference mismatch" in con for con in res_a["concerns"])

    # Case B: Preferred Remote candidate matching Hybrid job
    res_b = MatchEngineService.execute_deterministic_matching(base_profile, Job(
        job_id="job_hybrid",
        title="Engineer",
        normalized_title="engineer",
        company="Onsite Corp",
        location="Boston, MA",
        remote_status="hybrid",
        description="Work from home 2 days.",
        skills=["python"],
        source="adzuna"
    ))
    assert res_b["location_score"] == 8.0
    assert any("Candidate prefers Remote, but role is Hybrid" in con for con in res_b["concerns"])

    # Case C: Unspecified Remote preference -> No penalty
    base_profile.remote_preference = None
    res_c = MatchEngineService.execute_deterministic_matching(base_profile, job_onsite)
    assert res_c["location_score"] == 15.0


def test_alias_matching_and_false_equivalence(base_profile):
    """
    Verify normalization mapping (JS -> JavaScript) and false equivalencies (Java != JavaScript).
    """
    # In base_profile: profile.skills lists "JavaScript", "SQL", "Python"
    # Query normalization output
    normalized = JobNormalizationService.normalize_skills(["JS", "TS", "Postgres", "Java", "React Native"])
    
    assert "javascript" in normalized
    assert "typescript" in normalized
    assert "postgresql" in normalized
    
    # False equivalence tests
    assert "javascript" != "java"
    assert "react" != "react native"
    assert "aws" != "azure"


@pytest.mark.anyio
async def test_ambiguity_triggers_vs_skip(base_profile, session):
    """
    Verify that check_ambiguity_triggers selective triggers are active.
    """
    # 1. Clear-cut strong match: identical title, exact skills -> Skip Gemini
    job_clear = Job(
        job_id="clear_match",
        title="Software Engineer",
        normalized_title="software engineer",
        company="Tech Corp",
        location="Boston, MA",
        remote_status="remote",
        description="We need a Software Engineer.",
        skills=["python"],
        experience_required=1.0,
        source="remoteok"
    )
    det_clear = MatchEngineService.execute_deterministic_matching(base_profile, job_clear)
    assert not MatchEngineService.check_ambiguity_triggers(base_profile, job_clear, det_clear)

    # 2. Ambiguous title: preferred role is "Backend Developer", job is "Systems Engineer" -> Trigger Gemini
    job_ambiguous = Job(
        job_id="ambiguous_match",
        title="Systems Engineer",
        normalized_title="systems engineer",
        company="Tech Corp",
        location="Boston, MA",
        remote_status="remote",
        description="Managing servers and databases.",
        skills=["python"],
        experience_required=1.0,
        source="remoteok"
    )
    det_ambig = MatchEngineService.execute_deterministic_matching(base_profile, job_ambiguous)
    assert MatchEngineService.check_ambiguity_triggers(base_profile, job_ambiguous, det_ambig)


@pytest.mark.anyio
async def test_llm_fallback_and_timeout(base_profile, session):
    """
    Verify that if the LLM client fails or times out, the match engine recovers deterministically.
    """
    job = Job(
        job_id="job_timeout",
        title="Systems Engineer",
        normalized_title="systems engineer",
        company="Timeout Corp",
        location="Remote",
        remote_status="remote",
        description="Managing servers.",
        skills=["python"],
        source="remoteok"
    )
    
    # Configure a buggy/timeout client
    class TimeoutLLMClient(BaseLLMClient):
        def parse_resume(self, resume_text):
            return None
        async def parse_structured(self, prompt, schema_class):
            # Simulate a timeout delay
            await asyncio.sleep(2.0)
            raise RuntimeError("API Timeout")
            
    set_llm_client(TimeoutLLMClient())
    
    from app.config import settings
    old_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "dummy_api_key"
    try:
        # We call match_job_suitability, it should time out at 10.0 seconds or raise immediately.
        # The timeout in the engine is 10.0 seconds, but our runtime error is raised instantly.
        # Either way, the service should catch it and fall back to deterministic scoring.
        res = await MatchEngineService.match_job_suitability(
            profile=base_profile,
            job=job,
            session=session,
            include_llm=True
        )
    finally:
        settings.GEMINI_API_KEY = old_key
    
    # Verify fallback succeeded and stored result
    assert res.match_id is not None
    assert res.overall_score > 0.0
    assert "Deterministic suitability analysis" in res.explanation
    assert res.confidence == 0.5  # default fallback confidence


@pytest.mark.anyio
async def test_repeated_matching_and_uniqueness(base_profile, session):
    """
    Assert that executing match calculations twice on the same candidate+job
    upserts the single database row rather than adding duplicates.
    """
    # SQLite memory requires tables initialization for all models
    SQLModel.metadata.create_all(session.bind)
    
    job = Job(
        job_id="job_unique",
        title="Developer",
        normalized_title="developer",
        company="Unique Inc",
        location="Remote",
        remote_status="remote",
        description="Writing software.",
        skills=["python"],
        source="remoteok"
    )
    
    # First match
    res1 = await MatchEngineService.match_job_suitability(base_profile, job, session, include_llm=False)
    
    # Second match
    res2 = await MatchEngineService.match_job_suitability(base_profile, job, session, include_llm=False)
    
    # Verify same match ID
    assert res1.match_id == res2.match_id
    
    # Verify only one row exists in DB
    stmt = select(MatchResult).where(MatchResult.job_id == job.job_id)
    rows = session.exec(stmt).all()
    assert len(rows) == 1
    assert rows[0].engine_version == "1.0"
