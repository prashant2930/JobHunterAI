from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List, Optional
import asyncio
import logging

from app.database import get_session
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.match import MatchResult, BatchMatchRequest, MatchSearchResponse
from app.services.match_engine import MatchEngineService

router = APIRouter()
logger = logging.getLogger("jobhunter")

@router.post("/matches/job/{job_id}", response_model=MatchResult)
async def match_single_job(
    job_id: str,
    include_llm: bool = True,
    session: Session = Depends(get_session)
):
    """
    Computes suitability rating for a specific stored job against the active candidate profile.
    Saves or updates the result in the database.
    """
    # 1. Fetch active candidate profile (must exist)
    profile = session.exec(select(CandidateProfile)).first()
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No candidate profile found. Please upload a resume first."
        )
        
    # 2. Fetch the target job
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job with ID '{job_id}' not found."
        )
        
    try:
        match_result = await MatchEngineService.match_job_suitability(
            profile=profile,
            job=job,
            session=session,
            include_llm=include_llm
        )
        return match_result
    except Exception as e:
        logger.error(f"Single job matching failed for job {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Suitability matching transaction failed: {e}"
        )


@router.post("/matches/search", response_model=MatchSearchResponse)
async def batch_match_jobs(
    request: BatchMatchRequest,
    session: Session = Depends(get_session)
):
    """
    Trigger batch matching for all stored jobs against the active candidate profile.
    Uses concurrency limit semaphore (5) to coordinate async API execution safely.
    """
    profile = session.exec(select(CandidateProfile)).first()
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No candidate profile found. Please upload a resume first."
        )
        
    # Fetch all stored jobs in the database
    jobs = session.exec(select(Job)).all()
    if not jobs:
        return MatchSearchResponse(
            jobs_processed=0,
            matches_created=0,
            matches_updated=0,
            matches=[]
        )
        
    # Concurrency limit wrapper to avoid hammering LLM endpoints
    semaphore = asyncio.Semaphore(5)
    
    async def sem_match(job: Job):
        async with semaphore:
            try:
                # Query if match already exists to track created vs updated counts
                stmt = select(MatchResult).where(
                    (MatchResult.candidate_profile_id == profile.candidate_profile_id) &
                    (MatchResult.job_id == job.job_id)
                )
                existing = session.exec(stmt).first()
                is_update = existing is not None
                
                res = await MatchEngineService.match_job_suitability(
                    profile=profile,
                    job=job,
                    session=session,
                    include_llm=request.include_llm_analysis
                )
                return res, is_update, None
            except Exception as e:
                logger.error(f"Batch matching failed for job {job.job_id}: {e}")
                return None, False, str(e)

    tasks = [sem_match(job) for job in jobs]
    results = await asyncio.gather(*tasks)
    
    matches_created = 0
    matches_updated = 0
    jobs_processed = 0
    matches_list = []
    
    for match, is_update, err in results:
        if match:
            jobs_processed += 1
            if is_update:
                matches_updated += 1
            else:
                matches_created += 1
            
            # Filter matches by minimum score
            if request.minimum_score is None or match.overall_score >= request.minimum_score:
                matches_list.append(match)
                
    # Sort matches by overall_score descending
    matches_list.sort(key=lambda m: m.overall_score, reverse=True)
    
    # Return top matched entities limited by request limit
    return MatchSearchResponse(
        jobs_processed=jobs_processed,
        matches_created=matches_created,
        matches_updated=matches_updated,
        matches=matches_list[:request.limit]
    )


@router.get("/matches", response_model=List[MatchResult])
def get_matches(
    limit: int = 50,
    min_score: Optional[float] = None,
    session: Session = Depends(get_session)
):
    """
    Retrieves ranked match results stored in the local database.
    """
    try:
        stmt = select(MatchResult)
        if min_score is not None:
            stmt = stmt.where(MatchResult.overall_score >= min_score)
            
        stmt = stmt.order_by(MatchResult.overall_score.desc()).limit(limit)
        results = session.exec(stmt).all()
        return results
    except Exception as e:
        logger.error(f"Retrieve matches list failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve matches list from database."
        )


@router.get("/matches/{match_id}", response_model=MatchResult)
def get_match_details(
    match_id: str,
    session: Session = Depends(get_session)
):
    """
    Retrieve complete score breakdown and analysis of a specific match profile.
    """
    try:
        match = session.get(MatchResult, match_id)
        if not match:
            raise HTTPException(
                status_code=404,
                detail=f"Match result with ID '{match_id}' not found."
            )
        return match
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retrieve match details failed for ID {match_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to load match details."
        )
