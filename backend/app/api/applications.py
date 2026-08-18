from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List, Optional
import logging

from datetime import datetime

from app.database import get_session
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.application import (
    Application,
    ApplicationFormField,
    ApplicationAnalyzeRequest,
    ApplicationApproveRequest,
    ApplicationResponse
)
from app.services.application_analyzer import ApplicationAnalyzerService

router = APIRouter()
logger = logging.getLogger("jobhunter")


@router.post("/applications/analyze", response_model=ApplicationResponse)
async def analyze_application(
    request: ApplicationAnalyzeRequest,
    session: Session = Depends(get_session)
):
    """
    Trigger application form field detection, CandidateProfile data mapping,
    and AI-assisted question suggestion for a specific target job.
    """
    # 1. Active candidate profile check
    profile = session.exec(select(CandidateProfile)).first()
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No candidate profile found. Please upload a resume first."
        )

    # 2. Target job check
    job = session.get(Job, request.job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID '{request.job_id}' not found."
        )

    try:
        application = await ApplicationAnalyzerService.analyze_job_application(
            job=job,
            profile=profile,
            session=session,
            application_url=request.application_url
        )
        stmt_fields = select(ApplicationFormField).where(ApplicationFormField.application_id == application.id)
        fields = list(session.exec(stmt_fields).all())
        return ApplicationResponse(
            id=application.id,
            job_id=application.job_id,
            candidate_profile_id=application.candidate_profile_id,
            application_url=application.application_url,
            platform=application.platform,
            status=application.status,
            created_at=application.created_at,
            updated_at=application.updated_at,
            fields=fields
        )
    except Exception as e:
        logger.error(f"Application analysis transaction failed for job {request.job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Application form analysis failed: {e}"
        )


@router.get("/applications", response_model=List[ApplicationResponse])
def get_applications(session: Session = Depends(get_session)):
    """
    Retrieve all analyzed job applications for the active candidate profile.
    """
    try:
        profile = session.exec(select(CandidateProfile)).first()
        if not profile:
            return []

        stmt = select(Application).where(Application.candidate_profile_id == str(profile.id)).order_by(Application.updated_at.desc())
        applications = session.exec(stmt).all()
        res = []
        for app_item in applications:
            stmt_fields = select(ApplicationFormField).where(ApplicationFormField.application_id == app_item.id)
            fields = list(session.exec(stmt_fields).all())
            res.append(ApplicationResponse(
                id=app_item.id,
                job_id=app_item.job_id,
                candidate_profile_id=app_item.candidate_profile_id,
                application_url=app_item.application_url,
                platform=app_item.platform,
                status=app_item.status,
                created_at=app_item.created_at,
                updated_at=app_item.updated_at,
                fields=fields
            ))
        return res
    except Exception as e:
        logger.error(f"Retrieve applications list failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to load applications list."
        )


@router.get("/applications/{application_id}", response_model=ApplicationResponse)
def get_application_detail(
    application_id: str,
    session: Session = Depends(get_session)
):
    """
    Retrieve full application field structure, mapped values, and approval status.
    """
    try:
        application = session.get(Application, application_id)
        if not application:
            raise HTTPException(
                status_code=404,
                detail=f"Application with ID '{application_id}' not found."
            )
        stmt_fields = select(ApplicationFormField).where(ApplicationFormField.application_id == application.id)
        fields = list(session.exec(stmt_fields).all())
        return ApplicationResponse(
            id=application.id,
            job_id=application.job_id,
            candidate_profile_id=application.candidate_profile_id,
            application_url=application.application_url,
            platform=application.platform,
            status=application.status,
            created_at=application.created_at,
            updated_at=application.updated_at,
            fields=fields
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retrieve application detail failed for {application_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to load application detail."
        )


@router.post("/applications/{application_id}/approve", response_model=ApplicationResponse)
def approve_application(
    application_id: str,
    request: Optional[ApplicationApproveRequest] = None,
    session: Session = Depends(get_session)
):
    """
    Approve an analyzed application package after human review of field values.
    CRITICAL: This changes internal status to APPROVED. It does NOT perform external web submission.
    """
    try:
        application = session.get(Application, application_id)
        if not application:
            raise HTTPException(
                status_code=404,
                detail=f"Application with ID '{application_id}' not found."
            )

        # Apply user field overrides / updates if provided
        if request and request.field_updates:
            for update in request.field_updates:
                field = session.get(ApplicationFormField, update.field_id)
                if field and field.application_id == application.id:
                    if update.current_value is not None:
                        field.current_value = update.current_value
                        field.source = "user_override"
                    if update.requires_review is not None:
                        field.requires_review = update.requires_review
                    session.add(field)

        # Mark all fields as reviewed upon human approval action
        for f in application.fields:
            f.requires_review = False
            session.add(f)

        application.status = "APPROVED"
        application.updated_at = datetime.utcnow()

        session.add(application)
        session.commit()
        session.refresh(application)

        stmt_fields = select(ApplicationFormField).where(ApplicationFormField.application_id == application.id)
        fields = list(session.exec(stmt_fields).all())

        return ApplicationResponse(
            id=application.id,
            job_id=application.job_id,
            candidate_profile_id=application.candidate_profile_id,
            application_url=application.application_url,
            platform=application.platform,
            status=application.status,
            created_at=application.created_at,
            updated_at=application.updated_at,
            fields=fields
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Application approval transaction failed for {application_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to approve application package."
        )


