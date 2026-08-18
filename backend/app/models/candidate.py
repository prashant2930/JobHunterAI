from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON
from pydantic import BaseModel, Field as PydanticField
from typing import List, Optional
from datetime import datetime

# ==========================================
# 1. API SCHEMAS (Pydantic Models)
# ==========================================

class EducationSchema(BaseModel):
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    graduation_year: Optional[int] = None

class ExperienceSchema(BaseModel):
    company: str
    role: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = PydanticField(default_factory=list)

class ProjectSchema(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: List[str] = PydanticField(default_factory=list)
    url: Optional[str] = None

class SkillsSchema(BaseModel):
    programming_languages: List[str] = PydanticField(default_factory=list)
    frameworks: List[str] = PydanticField(default_factory=list)
    libraries: List[str] = PydanticField(default_factory=list)
    databases: List[str] = PydanticField(default_factory=list)
    cloud: List[str] = PydanticField(default_factory=list)
    tools: List[str] = PydanticField(default_factory=list)
    other_skills: List[str] = PydanticField(default_factory=list)

class PersonalInfoSchema(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None

class AdditionalInfoSchema(BaseModel):
    achievements: List[str] = PydanticField(default_factory=list)
    languages: List[str] = PydanticField(default_factory=list)
    links: List[str] = PydanticField(default_factory=list)

class UserPreferencesSchema(BaseModel):
    preferred_roles: List[str] = PydanticField(default_factory=list)
    preferred_locations: List[str] = PydanticField(default_factory=list)
    remote_preference: Optional[str] = None  # e.g., "remote", "hybrid", "onsite", "any"
    experience_level: Optional[str] = None  # e.g., "intern", "entry", "mid", "senior", "lead"
class ResumeExtractionSchema(BaseModel):
    version: str = "1.0"
    personal_info: PersonalInfoSchema
    education: List[EducationSchema] = PydanticField(default_factory=list)
    skills: SkillsSchema = PydanticField(default_factory=SkillsSchema)
    experience: List[ExperienceSchema] = PydanticField(default_factory=list)
    projects: List[ProjectSchema] = PydanticField(default_factory=list)
    certifications: List[str] = PydanticField(default_factory=list)
    additional_info: AdditionalInfoSchema = PydanticField(
        default_factory=AdditionalInfoSchema
    )
class CandidateProfileSchema(BaseModel):
    version: str = "1.0"
    personal_info: PersonalInfoSchema
    education: List[EducationSchema] = PydanticField(default_factory=list)
    skills: SkillsSchema = PydanticField(default_factory=SkillsSchema)
    experience: List[ExperienceSchema] = PydanticField(default_factory=list)
    projects: List[ProjectSchema] = PydanticField(default_factory=list)
    certifications: List[str] = PydanticField(default_factory=list)
    additional_info: AdditionalInfoSchema = PydanticField(default_factory=AdditionalInfoSchema)
    
    # Preferences (must NOT be populated by Gemini extraction)
    preferences: UserPreferencesSchema = PydanticField(default_factory=UserPreferencesSchema)
    
    # Metadata to track sources
    profile_source: str = "extracted"  # "extracted" or "user_provided"
    preferences_source: str = "none"   # "none" or "user_provided"


# ==========================================
# 2. DATABASE MODELS (SQLModel Entities)
# ==========================================

class CandidateProfile(SQLModel, table=True):
    __tablename__ = "candidate_profile"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    
    # JSON columns for arrays in SQLite
    certifications: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills_programming_languages: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills_frameworks: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills_libraries: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills_databases: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills_cloud: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills_tools: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills_others: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    achievements: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    languages: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    links: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    # User provided preferences
    preferred_roles: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    preferred_locations: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    remote_preference: Optional[str] = None
    experience_level: Optional[str] = None
    
    # Tracking fields
    profile_source: str = Field(default="extracted")  # "extracted" or "user_provided"
    preferences_source: str = Field(default="none")   # "none" or "user_provided"
    
    is_active: bool = Field(default=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships (cascade deletes children when parent profile is deleted)
    education: List["EducationRecord"] = Relationship(
        back_populates="profile",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    experience: List["ExperienceRecord"] = Relationship(
        back_populates="profile",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    projects: List["ProjectRecord"] = Relationship(
        back_populates="profile",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class EducationRecord(SQLModel, table=True):
    __tablename__ = "education_record"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="candidate_profile.id")
    
    institution: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    graduation_year: Optional[int] = None
    
    profile: Optional[CandidateProfile] = Relationship(back_populates="education")


class ExperienceRecord(SQLModel, table=True):
    __tablename__ = "experience_record"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="candidate_profile.id")
    
    company: str
    role: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    profile: Optional[CandidateProfile] = Relationship(back_populates="experience")


class ProjectRecord(SQLModel, table=True):
    __tablename__ = "project_record"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="candidate_profile.id")
    
    name: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    url: Optional[str] = None
    
    profile: Optional[CandidateProfile] = Relationship(back_populates="projects")
