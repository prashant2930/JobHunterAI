from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

# ==========================================
# 1. DATABASE MODELS (SQLModel Entities)
# ==========================================

class Job(SQLModel, table=True):
    __tablename__ = "job"
    
    job_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), 
        primary_key=True,
        index=True
    )
    
    source: str = Field(index=True)
    source_job_id: str = Field(index=True)
    
    # Store both original and normalized values (required for comparison & tracking)
    title: str = Field(index=True)
    normalized_title: str = Field(index=True)
    
    company: str = Field(index=True)
    normalized_company: str = Field(index=True)
    
    location: str = Field(index=True)
    normalized_location: str = Field(index=True)
    
    remote_status: str = Field(default="unspecified")  # "remote", "hybrid", "onsite", "unspecified"
    
    description: str
    requirements: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    preferred_qualifications: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    experience_required: Optional[float] = None
    employment_type: str = Field(default="unspecified")  # "full-time", "part-time", "contract", "internship", "unspecified"
    
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    
    posted_date: Optional[datetime] = Field(default=None, index=True)
    application_url: str = Field(index=True)
    
    # Provenance tracking
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    collected_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# 2. API REQUEST / RESPONSE SCHEMAS
# ==========================================

class JobSearchRequest(BaseModel):
    query: str
    location: Optional[str] = None
    remote: Optional[str] = None  # "remote", "hybrid", "onsite", "any"
    page: int = 1
    limit: int = 10
    max_pages: int = 1

class DuplicateRecordInfo(BaseModel):
    title: str
    company: str
    sources: List[str]
    canonical_url: str
    detected_at: str

class JobSearchResponse(BaseModel):
    jobs_found: int
    new_jobs: int
    duplicates_removed: int
    errors: dict  # e.g., {"Adzuna": "Connection timed out"}
    jobs: List[Job]
    duplicate_records: List[DuplicateRecordInfo] = []

