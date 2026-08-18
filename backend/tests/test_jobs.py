import pytest
import asyncio
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from sqlmodel import Session, SQLModel, create_engine, select, text
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session, engine, init_db
from app.models.job import Job, JobSearchRequest
from app.services.normalization import JobNormalizationService
from app.services.deduplication import JobDeduplicationService, levenshtein_ratio
from app.services.job_aggregator import JobAggregatorService
from app.scrapers.base import BaseJobSource

# ==========================================
# 1. Normalization Unit Tests
# ==========================================

def test_company_normalization():
    assert JobNormalizationService.normalize_company("Google LLC") == "google"
    assert JobNormalizationService.normalize_company("Google, Inc.") == "google"
    assert JobNormalizationService.normalize_company("Stripe Corporation") == "stripe"
    assert JobNormalizationService.normalize_company("ACME Ltd.") == "acme"
    assert JobNormalizationService.normalize_company("Acme Limited") == "acme"

def test_title_normalization():
    assert JobNormalizationService.normalize_title("Software Engineer II (React)") == "software engineer ii react"
    assert JobNormalizationService.normalize_title("Senior Python Developer - Django") == "senior python developer - django"

def test_location_normalization():
    assert JobNormalizationService.normalize_location("Boston, MA") == "boston, ma"
    assert JobNormalizationService.normalize_location("Work From Home - Virtual") == "remote"
    assert JobNormalizationService.normalize_location("Anywhere, US") == "remote"

def test_skills_normalization():
    raw_skills = ["js", "TS", "Postgres", "AWS", "reactjs", "VueJS", "Python"]
    normalized = JobNormalizationService.normalize_skills(raw_skills)
    
    assert "javascript" in normalized
    assert "typescript" in normalized
    assert "postgresql" in normalized
    assert "amazon web services" in normalized
    assert "react" in normalized
    assert "vue" in normalized
    assert "python" in normalized  # unaffected, but lowercased


# ==========================================
# 2. Conservative Deduplication Unit Tests
# ==========================================

def test_dedup_level1_url():
    """Verify that same application URL always maps as duplicate."""
    job1 = Job(
        source="adzuna", source_job_id="1", title="Dev", company="A", location="Remote", 
        normalized_company="a", normalized_title="dev", normalized_location="remote",
        description="desc a", application_url="https://dup.com"
    )
    job2 = Job(
        source="remoteok", source_job_id="2", title="Dev", company="B", location="Remote", 
        normalized_company="b", normalized_title="dev", normalized_location="remote",
        description="desc b", application_url="https://dup.com"
    )
    is_dup, reason = JobDeduplicationService.check_duplicate(job1, job2)
    assert is_dup is True
    assert reason == "duplicate_application_url"

def test_dedup_level1_source_id():
    """Verify that same source + source_job_id maps as duplicate."""
    job1 = Job(
        source="adzuna", source_job_id="101", title="Dev", company="A", location="Remote", 
        normalized_company="a", normalized_title="dev", normalized_location="remote",
        description="desc a", application_url="https://url1.com"
    )
    job2 = Job(
        source="adzuna", source_job_id="101", title="Developer", company="A", location="Remote", 
        normalized_company="a", normalized_title="developer", normalized_location="remote",
        description="desc a", application_url="https://url2.com"
    )
    is_dup, reason = JobDeduplicationService.check_duplicate(job1, job2)
    assert is_dup is True
    assert reason == "duplicate_source_job_id"

def test_dedup_level2_generic_title_false_positives():
    """Verify that distinct roles with similar titles at same company are NOT merged."""
    # Case A: Title difference (e.g. Software Engineer vs Senior Software Engineer)
    job1 = Job(
        source="adzuna", source_job_id="1", title="Software Engineer", company="Stripe", location="SF",
        normalized_company="stripe", normalized_title="software engineer", normalized_location="sf",
        description="Write Python code for billing API", application_url="https://stripe.com/1"
    )
    job2 = Job(
        source="adzuna", source_job_id="2", title="Senior Software Engineer", company="Stripe", location="SF",
        normalized_company="stripe", normalized_title="senior software engineer", normalized_location="sf",
        description="Lead billing API architecture using Python", application_url="https://stripe.com/2"
    )
    
    is_dup, _ = JobDeduplicationService.check_duplicate(job1, job2)
    assert is_dup is False  # Must not merge Junior/Senior roles
    
    # Case B: Same company, location, and title but different descriptions (separate job openings)
    job3 = Job(
        source="adzuna", source_job_id="3", title="Backend Engineer", company="Stripe", location="SF",
        normalized_company="stripe", normalized_title="backend engineer", normalized_location="sf",
        description="Looking for Python backend engineers to help with billing operations.", application_url="https://stripe.com/3"
    )
    job4 = Job(
        source="adzuna", source_job_id="4", title="Backend Engineer", company="Stripe", location="SF",
        normalized_company="stripe", normalized_title="backend engineer", normalized_location="sf",
        description="Looking for Java system engineers to rebuild core ledger infrastructure.", application_url="https://stripe.com/4"
    )
    
    is_dup, _ = JobDeduplicationService.check_duplicate(job3, job4)
    assert is_dup is False  # Must not merge since description/technology focuses are completely different


# ==========================================
# 3. Repeated Ingestion & Mock Source Tests
# ==========================================

class FakeJobSource(BaseJobSource):
    async def search_jobs(self, query: str, location=None, remote=None, page=1, limit=10):
        return [
            {
                "source": "fake",
                "source_job_id": "fake_1",
                "title": "React Engineer",
                "company": "HubSpot",
                "location": "Boston, MA",
                "remote_status": "remote",
                "description": "We are seeking a frontend specialist with expertise in React.",
                "application_url": "https://hubspot.com/careers/1",
                "posted_date": "2026-08-12T00:00:00Z"
            },
            {
                "source": "fake",
                "source_job_id": "fake_2",
                "title": "Python Engineer",
                "company": "HubSpot",
                "location": "Boston, MA",
                "remote_status": "onsite",
                "description": "We are seeking a backend engineer with Python skills.",
                "application_url": "https://hubspot.com/careers/2",
                "posted_date": "2026-08-12T00:00:00Z"
            }
        ]

@pytest.mark.anyio
async def test_repeated_ingestion_updates_timestamps():
    """Verify second ingestion pass doesn't write new jobs, but updates last_seen_at."""
    # Create clean in-memory database
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        aggregator = JobAggregatorService()
        # Mock aggregator sources list with FakeJobSource
        aggregator.sources = [FakeJobSource()]
        
        # Pass 1: Fresh aggregation
        result1 = await aggregator.aggregate_jobs(
            query="developer",
            session=session
        )
        assert result1["new_jobs"] == 2
        assert result1["duplicates_removed"] == 0
        
        # Load jobs from memory database
        jobs_p1 = session.exec(select(Job)).all()
        assert len(jobs_p1) == 2
        
        orig_first_seen = {j.job_id: j.first_seen_at for j in jobs_p1}
        orig_last_seen = {j.job_id: j.last_seen_at for j in jobs_p1}
        
        # Pause briefly to ensure clock shifts forward
        await asyncio.sleep(0.01)
        
        # Pass 2: Repeated Aggregation
        result2 = await aggregator.aggregate_jobs(
            query="developer",
            session=session
        )
        assert result2["new_jobs"] == 0
        assert result2["duplicates_removed"] == 2
        
        # Reload jobs from memory
        jobs_p2 = session.exec(select(Job)).all()
        assert len(jobs_p2) == 2
        
        for j in jobs_p2:
            # first_seen_at must remain exactly identical
            assert j.first_seen_at == orig_first_seen[j.job_id]
            # last_seen_at must have been updated to a newer timestamp
            assert j.last_seen_at > orig_last_seen[j.job_id]


# ==========================================
# 4. API Endpoints Integration Tests
# ==========================================

def test_api_jobs_endpoints():
    # Make sure database tables are initialized
    init_db()
    
    # Clean up any existing job listings in test db
    with Session(engine) as session:
        session.exec(text("DELETE FROM job"))
        session.commit()
        
    client = TestClient(app)
    
    # 1. Verify GET /api/jobs is empty initially
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert response.json() == []
    
    # 2. Ingest jobs via search using Mock sources patching
    class MockAdzunaSource:
        async def search_jobs(self, query: str, location=None, remote=None, page=1, limit=10):
            return [
                {
                    "source": "adzuna",
                    "source_job_id": "adzuna_1",
                    "title": "React Engineer",
                    "company": "HubSpot",
                    "location": "Boston, MA",
                    "remote_status": "remote",
                    "description": "We are seeking a frontend specialist with expertise in React.",
                    "application_url": "https://hubspot.com/careers/1",
                    "posted_date": "2026-08-12T00:00:00Z"
                }
            ]

    class MockRemoteOKSource:
        async def search_jobs(self, query: str, location=None, remote=None, page=1, limit=10):
            return [
                {
                    "source": "remoteok",
                    "source_job_id": "remoteok_1",
                    "title": "Python Engineer",
                    "company": "HubSpot",
                    "location": "Boston, MA",
                    "remote_status": "onsite",
                    "description": "We are seeking a backend engineer with Python skills.",
                    "application_url": "https://hubspot.com/careers/2",
                    "posted_date": "2026-08-12T00:00:00Z"
                }
            ]

    mock_sources = [MockAdzunaSource(), MockRemoteOKSource()]
    with patch.object(JobAggregatorService, "__init__", lambda self: setattr(self, "sources", mock_sources)):
        response = client.post(
            "/api/jobs/search",
            json={"query": "React", "max_pages": 1}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["jobs_found"] == 2
        assert data["new_jobs"] == 2
        assert data["duplicates_removed"] == 0
        
    # 3. Verify GET /api/jobs now retrieves jobs and filters work
    response = client.get("/api/jobs")
    assert response.status_code == 200
    db_jobs = response.json()
    assert len(db_jobs) == 2
    
    job_react = next(j for j in db_jobs if "React" in j["title"])
    job_python = next(j for j in db_jobs if "Python" in j["title"])
    
    # Test detail API
    detail_res = client.get(f"/api/jobs/{job_react['job_id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["title"] == "React Engineer"
    
    # Test filters
    filter_res = client.get("/api/jobs?remote=onsite")
    assert filter_res.status_code == 200
    assert len(filter_res.json()) == 1
    assert filter_res.json()[0]["title"] == "Python Engineer"
    
    # Cleanup: remove inserted jobs
    with Session(engine) as session:
        session.exec(text("DELETE FROM job"))
        session.commit()
