from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List, Optional
import logging

from app.database import get_session
from app.models.job import Job, JobSearchRequest, JobSearchResponse
from app.services.job_aggregator import JobAggregatorService

router = APIRouter()
logger = logging.getLogger("jobhunter")

@router.post("/jobs/search", response_model=JobSearchResponse)
async def search_jobs(
    request: JobSearchRequest,
    session: Session = Depends(get_session)
):
    """
    Trigger job aggregation pipeline across active sources.
    Returns counts of new jobs, duplicates removed, and source errors.
    """
    try:
        aggregator = JobAggregatorService()
        result = await aggregator.aggregate_jobs(
            query=request.query,
            location=request.location,
            remote=request.remote,
            page=request.page,
            limit=request.limit,
            max_pages=request.max_pages,
            session=session
        )
        return result
    except Exception as e:
        logger.error(f"Search API request failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during job discovery: {e}"
        )


@router.get("/jobs", response_model=List[Job])
def get_jobs(
    page: int = 1,
    limit: int = 10,
    source: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    remote: Optional[str] = None,
    title: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Retrieves a list of normalized job openings from the local database.
    Supports pagination and filters.
    """
    try:
        stmt = select(Job)
        
        # Apply filters conditionally
        if source:
            stmt = stmt.where(Job.source == source)
        if company:
            stmt = stmt.where(Job.company.ilike(f"%{company}%"))
        if location:
            stmt = stmt.where(Job.location.ilike(f"%{location}%"))
        if remote and remote != "any":
            stmt = stmt.where(Job.remote_status == remote)
        if title:
            stmt = stmt.where(Job.title.ilike(f"%{title}%"))
            
        # Order by posted_date descending (null values placed last)
        stmt = stmt.order_by(Job.posted_date.desc())
        
        # Paginate results
        stmt = stmt.offset((page - 1) * limit).limit(limit)
        
        jobs = session.exec(stmt).all()
        return jobs
        
    except Exception as e:
        logger.error(f"Retrieve jobs list failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve jobs list from database."
        )


@router.get("/jobs/{job_id}", response_model=Job)
def get_job_detail(
    job_id: str,
    session: Session = Depends(get_session)
):
    """
    Retrieves full details of a specific job by its local unique identifier.
    """
    try:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job with ID '{job_id}' not found."
            )
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retrieve job details failed for {job_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to load job details."
        )
