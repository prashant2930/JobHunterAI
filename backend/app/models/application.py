from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

# ==========================================
# 1. DATABASE MODELS (SQLModel Entities)
# ==========================================

class Application(SQLModel, table=True):
    __tablename__ = "application"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        index=True
    )
    job_id: str = Field(foreign_key="job.job_id", index=True)
    candidate_profile_id: str = Field(index=True)
    application_url: str = Field(default="")
    platform: str = Field(default="generic")
    status: str = Field(default="READY_FOR_REVIEW", index=True)  # DISCOVERED, ANALYZING, READY_FOR_REVIEW, APPROVED, FAILED

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    fields: List["ApplicationFormField"] = Relationship(
        back_populates="application",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class ApplicationFormField(SQLModel, table=True):
    __tablename__ = "application_form_field"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        index=True
    )
    application_id: str = Field(foreign_key="application.id", index=True)

    field_name: str
    label: str
    field_type: str = Field(default="TEXT")  # TEXT, EMAIL, PHONE, NUMBER, DATE, SELECT, RADIO, CHECKBOX, TEXTAREA, FILE_UPLOAD
    required: bool = Field(default=False)
    options: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    current_value: Optional[str] = None
    suggested_value: Optional[str] = None
    source: str = Field(default="unknown")  # candidate_profile, llm_generated, user_override, unknown
    confidence: float = Field(default=1.0)
    requires_review: bool = Field(default=False)

    application: Optional[Application] = Relationship(back_populates="fields")


# ==========================================
# 2. API REQUEST / RESPONSE SCHEMAS
# ==========================================

class ApplicationAnalyzeRequest(BaseModel):
    job_id: str
    application_url: Optional[str] = None

class ApplicationFieldUpdate(BaseModel):
    field_id: str
    current_value: Optional[str] = None
    requires_review: Optional[bool] = None

class ApplicationApproveRequest(BaseModel):
    field_updates: Optional[List[ApplicationFieldUpdate]] = None

class QuestionAnswerSchema(BaseModel):
    suggested_answer: str
    confidence: float
    requires_review: bool
    reasoning: str

class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    candidate_profile_id: str
    application_url: str
    platform: str
    status: str
    created_at: datetime
    updated_at: datetime
    fields: List[ApplicationFormField] = []

