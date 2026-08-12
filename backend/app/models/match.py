from enum import Enum
from sqlmodel import SQLModel, Field, UniqueConstraint
from sqlalchemy import Column, JSON
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

# ==========================================
# 1. ENUMS AND UTILITIES
# ==========================================

class RecommendationEnum(str, Enum):
    STRONG_MATCH = "STRONG_MATCH"
    MATCH = "MATCH"
    POSSIBLE = "POSSIBLE"
    WEAK_MATCH = "WEAK_MATCH"
    REJECT = "REJECT"


# ==========================================
# 2. DATABASE MODELS (SQLModel Entities)
# ==========================================

class MatchResult(SQLModel, table=True):
    __tablename__ = "match_result"
    
    # Enforce unique candidate_profile + job pairing
    __table_args__ = (
        UniqueConstraint(
            "candidate_profile_id", 
            "job_id", 
            name="uq_candidate_profile_job_match"
        ),
    )
    
    match_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), 
        primary_key=True,
        index=True
    )
    
    job_id: str = Field(index=True)
    candidate_profile_id: str = Field(index=True)
    
    overall_score: float = Field(index=True)
    recommendation: RecommendationEnum = Field(index=True)
    
    # Configurable score splits out of 100
    skill_score: float
    experience_score: float
    education_score: float
    role_score: float
    location_score: float
    required_qualification_score: float  # compliance penalty triggers
    preferred_qualification_score: float
    
    # Relational JSON list columns
    matching_skills: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    missing_required_skills: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    missing_preferred_skills: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    experience_gap: float = 0.0
    concerns: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    explanation: str
    confidence: float = 1.0
    
    engine_version: str = Field(default="1.0")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# 3. API REQUEST / RESPONSE SCHEMAS
# ==========================================

class BatchMatchRequest(BaseModel):
    minimum_score: Optional[float] = 0.0
    limit: int = 20
    include_llm_analysis: bool = True

class MatchSearchResponse(BaseModel):
    jobs_processed: int
    matches_created: int
    matches_updated: int
    matches: List[MatchResult]
