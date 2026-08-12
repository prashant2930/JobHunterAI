from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlmodel import Session, select
from typing import Optional
import logging

from app.database import get_session
from app.models.candidate import (
    CandidateProfile,
    EducationRecord,
    ExperienceRecord,
    ProjectRecord,
    CandidateProfileSchema,
    PersonalInfoSchema,
    EducationSchema,
    SkillsSchema,
    ExperienceSchema,
    ProjectSchema,
    AdditionalInfoSchema,
    UserPreferencesSchema
)
from app.services.resume_parser import DocumentExtractor
from app.services.llm_client import get_llm_client

router = APIRouter()
logger = logging.getLogger("jobhunter")

# File size limits (5MB maximum size limit)
MAX_FILE_SIZE = 5 * 1024 * 1024

def db_to_schema(profile: CandidateProfile) -> CandidateProfileSchema:
    """
    Utility to map CandidateProfile DB model to CandidateProfileSchema Pydantic model.
    """
    return CandidateProfileSchema(
        version="1.0",
        personal_info=PersonalInfoSchema(
            name=profile.name,
            email=profile.email,
            phone=profile.phone,
            location=profile.location
        ),
        education=[
            EducationSchema(
                institution=edu.institution,
                degree=edu.degree,
                field_of_study=edu.field_of_study,
                graduation_year=edu.graduation_year
            ) for edu in profile.education
        ],
        skills=SkillsSchema(
            programming_languages=profile.skills_programming_languages,
            frameworks=profile.skills_frameworks,
            libraries=profile.skills_libraries,
            databases=profile.skills_databases,
            cloud=profile.skills_cloud,
            tools=profile.skills_tools,
            other_skills=profile.skills_others
        ),
        experience=[
            ExperienceSchema(
                company=exp.company,
                role=exp.role,
                location=exp.location,
                start_date=exp.start_date,
                end_date=exp.end_date,
                description=exp.description,
                technologies=exp.technologies
            ) for exp in profile.experience
        ],
        projects=[
            ProjectSchema(
                name=proj.name,
                description=proj.description,
                technologies=proj.technologies,
                url=proj.url
            ) for proj in profile.projects
        ],
        certifications=profile.certifications,
        additional_info=AdditionalInfoSchema(
            achievements=profile.achievements,
            languages=profile.languages,
            links=profile.links
        ),
        preferences=UserPreferencesSchema(
            preferred_roles=profile.preferred_roles,
            preferred_locations=profile.preferred_locations,
            remote_preference=profile.remote_preference,
            experience_level=profile.experience_level
        ),
        profile_source=profile.profile_source,
        preferences_source=profile.preferences_source
    )


@router.post("/profile/resume", response_model=CandidateProfileSchema)
async def upload_resume(file: UploadFile = File(...)):
    """
    Ingests resume PDF/DOCX, extracts text locally, and parses structured schema via LLM.
    Does NOT write to database. Returns JSON for user review in the UI.
    """
    # 1. Validate file extension
    filename = file.filename or "resume.pdf"
    ext = filename.split(".")[-1].lower()
    if ext not in ["pdf", "docx"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Only PDF and DOCX documents are supported."
        )

    # 2. Enforce size limit
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds limit. Maximum allowed size is 5MB."
        )
        
    try:
        # 3. Local text extraction
        extracted_text = DocumentExtractor.extract(filename, file_bytes)
        
        # 4. LLM parsing (calls BaseLLMClient interface method)
        llm_client = get_llm_client()
        profile_schema = llm_client.parse_resume(extracted_text)
        return profile_schema
        
    except ValueError as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        # Raised by get_llm_client() when no valid API key is configured,
        # or by GeminiClient when structured parsing fails.
        logger.error(f"LLM service unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Resume processing pipeline failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process resume. Check backend logs for details."
        )


@router.get("/profile", response_model=Optional[CandidateProfileSchema])
def get_profile(session: Session = Depends(get_session)):
    """
    Retrieves the currently active candidate profile from the SQLite database.
    Returns None if no profile is set.
    """
    try:
        db_profile = session.exec(
            select(CandidateProfile)
            .where(CandidateProfile.is_active == True)
        ).first()
        
        if not db_profile:
            return None
            
        return db_to_schema(db_profile)
    except Exception as e:
        logger.error(f"Failed to fetch profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database fetch failed.")


@router.post("/profile", response_model=CandidateProfileSchema)
def save_profile(
    profile_schema: CandidateProfileSchema,
    session: Session = Depends(get_session)
):
    """
    Saves the user-reviewed candidate profile.
    Sets existing profiles to inactive and commits the new authoritative profile.
    """
    try:
        # 1. Mark existing active profiles as inactive
        active_profiles = session.exec(
            select(CandidateProfile)
            .where(CandidateProfile.is_active == True)
        ).all()
        for p in active_profiles:
            p.is_active = False
            session.add(p)
            
        # 2. Deduce preference sources (marked as user_provided if filled by the user)
        has_preferences = bool(
            profile_schema.preferences.preferred_roles or
            profile_schema.preferences.preferred_locations or
            profile_schema.preferences.remote_preference or
            profile_schema.preferences.experience_level
        )
        
        # 3. Create database entry
        db_profile = CandidateProfile(
            name=profile_schema.personal_info.name,
            email=profile_schema.personal_info.email,
            phone=profile_schema.personal_info.phone,
            location=profile_schema.personal_info.location,
            certifications=profile_schema.certifications,
            skills_programming_languages=profile_schema.skills.programming_languages,
            skills_frameworks=profile_schema.skills.frameworks,
            skills_libraries=profile_schema.skills.libraries,
            skills_databases=profile_schema.skills.databases,
            skills_cloud=profile_schema.skills.cloud,
            skills_tools=profile_schema.skills.tools,
            skills_others=profile_schema.skills.other_skills,
            achievements=profile_schema.additional_info.achievements,
            languages=profile_schema.additional_info.languages,
            links=profile_schema.additional_info.links,
            preferred_roles=profile_schema.preferences.preferred_roles,
            preferred_locations=profile_schema.preferences.preferred_locations,
            remote_preference=profile_schema.preferences.remote_preference,
            experience_level=profile_schema.preferences.experience_level,
            profile_source="user_provided",  # Marked as user provided on save approval
            preferences_source="user_provided" if has_preferences else "none",
            is_active=True
        )
        
        # 4. Attach associated records
        for edu in profile_schema.education:
            db_profile.education.append(
                EducationRecord(
                    institution=edu.institution,
                    degree=edu.degree,
                    field_of_study=edu.field_of_study,
                    graduation_year=edu.graduation_year
                )
            )
            
        for exp in profile_schema.experience:
            db_profile.experience.append(
                ExperienceRecord(
                    company=exp.company,
                    role=exp.role,
                    location=exp.location,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    description=exp.description,
                    technologies=exp.technologies
                )
            )
            
        for proj in profile_schema.projects:
            db_profile.projects.append(
                ProjectRecord(
                    name=proj.name,
                    description=proj.description,
                    technologies=proj.technologies,
                    url=proj.url
                )
            )
            
        session.add(db_profile)
        session.commit()
        session.refresh(db_profile)
        
        logger.info(f"Successfully saved candidate profile ID {db_profile.id} to SQLite.")
        return db_to_schema(db_profile)
        
    except Exception as e:
        logger.error(f"Failed to save profile: {e}", exc_info=True)
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save profile: {e}"
        )
