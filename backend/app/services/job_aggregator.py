import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlmodel import Session, select

from app.models.job import Job
from app.services.normalization import JobNormalizationService
from app.services.deduplication import JobDeduplicationService
from app.scrapers.adzuna import AdzunaSource
from app.scrapers.remoteok import RemoteOKSource
from app.scrapers.arbeitnow import ArbeitnowSource
from app.scrapers.remotive import RemotiveSource
from app.scrapers.jobicy import JobicySource
from app.scrapers.greenhouse import GreenhousePublicSource
from app.scrapers.lever import LeverPublicSource

logger = logging.getLogger("jobhunter")

class JobAggregatorService:
    """
    Orchestrates the job discovery, normalization, deduplication, and database ingestion pipeline.
    """
    
    def __init__(self):
        # Register available job search adapters
        self.sources = [
            AdzunaSource(),
            RemoteOKSource(),
            ArbeitnowSource(),
            RemotiveSource(),
            JobicySource(),
            GreenhousePublicSource(),
            LeverPublicSource()
        ]


    async def _fetch_source(
        self, 
        source_client, 
        query: str, 
        location: Optional[str], 
        remote: Optional[str], 
        page: int, 
        limit: int
    ) -> tuple:
        """
        Safely calls an individual job source. Catches any exception to prevent complete search failure.
        """
        source_name = source_client.__class__.__name__.replace("Source", "")
        try:
            results = await source_client.search_jobs(
                query=query, 
                location=location, 
                remote=remote, 
                page=page, 
                limit=limit
            )
            return results, source_name, None
        except Exception as e:
            logger.error(f"Job source {source_name} failed during fetch: {e}")
            return [], source_name, str(e)

    async def aggregate_jobs(
        self, 
        query: str, 
        location: Optional[str] = None, 
        remote: Optional[str] = None, 
        page: int = 1, 
        limit: int = 10, 
        max_pages: int = 1,
        session: Optional[Session] = None
    ) -> Dict:
        """
        Ingests search parameters, fetches jobs concurrently across pages,
        normalizes attributes, filters duplicate listings, and stores unique results in SQLite.
        """
        if not session:
            raise ValueError("Aggregator requires a valid database session.")
            
        jobs_found = 0
        new_jobs_count = 0
        duplicates_removed = 0
        errors = {}
        processed_jobs: List[Job] = []
        duplicate_records_list: List[Dict] = []
        
        # Ingest jobs page by page
        for p in range(page, page + max_pages):
            # Formulate concurrent tasks for the page
            tasks = [
                self._fetch_source(source, query, location, remote, p, limit) 
                for source in self.sources
            ]
            
            # Execute queries concurrently
            fetched_results = await asyncio.gather(*tasks)
            
            for raw_jobs, source_name, err in fetched_results:
                if err:
                    errors[source_name] = err
                    continue
                    
                for raw_job in raw_jobs:
                    # 0. Fast Relevance check
                    if not JobNormalizationService.is_job_relevant(
                        title=raw_job.get("title", ""),
                        query=query
                    ):
                        continue

                    jobs_found += 1
                    
                    # 1. Normalize variables for indexing/comparison
                    norm_title = JobNormalizationService.normalize_title(raw_job.get("title", ""))
                    norm_company = JobNormalizationService.normalize_company(raw_job.get("company", ""))
                    norm_location = JobNormalizationService.normalize_location(raw_job.get("location", ""))
                    norm_skills = JobNormalizationService.normalize_skills(raw_job.get("skills", []))

                    exp_req = raw_job.get("experience_required")
                    if exp_req is None:
                        exp_req = JobNormalizationService.extract_experience_years(
                            raw_job.get("title", ""),
                            raw_job.get("description", "")
                        )
                    
                    # 2. Parse raw posted date string
                    parsed_posted_date = None
                    posted_raw = raw_job.get("posted_date")
                    if posted_raw:
                        try:
                            # Standard isoformat parsing (handling timezone offsets)
                            if posted_raw.endswith("Z"):
                                posted_raw = posted_raw[:-1] + "+00:00"
                            parsed_posted_date = datetime.fromisoformat(posted_raw)
                        except Exception:
                            logger.warning(f"Could not parse posted date string: {posted_raw}. Defaulting to None.")
                    
                    # 3. Construct Pydantic Job model instance
                    new_job = Job(
                        source=raw_job.get("source", "unknown"),
                        source_job_id=raw_job.get("source_job_id", ""),
                        title=raw_job.get("title", "Untitled"),
                        normalized_title=norm_title,
                        company=raw_job.get("company", "Unknown"),
                        normalized_company=norm_company,
                        location=raw_job.get("location", "Unknown"),
                        normalized_location=norm_location,
                        remote_status=raw_job.get("remote_status", "unspecified"),
                        description=raw_job.get("description", ""),
                        requirements=raw_job.get("requirements", []),
                        preferred_qualifications=raw_job.get("preferred_qualifications", []),
                        skills=norm_skills,
                        experience_required=exp_req,

                        employment_type=raw_job.get("employment_type", "unspecified"),
                        salary_min=raw_job.get("salary_min"),
                        salary_max=raw_job.get("salary_max"),
                        salary_currency=raw_job.get("salary_currency"),
                        posted_date=parsed_posted_date,
                        application_url=raw_job.get("application_url", ""),
                        first_seen_at=datetime.utcnow(),
                        last_seen_at=datetime.utcnow(),
                        collected_at=datetime.utcnow()
                    )
                    
                    # 4. Perform Conservative Deduplication against database
                    # Query potential duplicates sharing same URL, source IDs, or company/location
                    stmt = select(Job).where(
                        (Job.application_url == new_job.application_url) |
                        ((Job.source == new_job.source) & (Job.source_job_id == new_job.source_job_id)) |
                        ((Job.normalized_company == new_job.normalized_company) & (Job.normalized_location == new_job.normalized_location))
                    )
                    existing_matches = session.exec(stmt).all()
                    
                    is_dup = False
                    dup_match_record = None
                    
                    for existing_job in existing_matches:
                        is_dup_check, reason = JobDeduplicationService.check_duplicate(new_job, existing_job)
                        if is_dup_check:
                            is_dup = True
                            dup_match_record = existing_job
                            break
                            
                    if is_dup and dup_match_record:
                        # Update last_seen_at for the duplicate record to track job freshness
                        dup_match_record.last_seen_at = datetime.utcnow()
                        session.add(dup_match_record)
                        duplicates_removed += 1
                        duplicate_records_list.append({
                            "title": new_job.title,
                            "company": new_job.company,
                            "sources": list(set([new_job.source, dup_match_record.source])),
                            "canonical_url": dup_match_record.application_url,
                            "detected_at": datetime.utcnow().isoformat()
                        })
                        logger.info(f"Duplicate job detected and updated: '{new_job.title}' at '{new_job.company}'.")
                    else:
                        # Write unique job to database
                        session.add(new_job)
                        processed_jobs.append(new_job)
                        new_jobs_count += 1
                        
            # Commit batch inserts for the page
            session.commit()
            
        return {
            "jobs_found": jobs_found,
            "new_jobs": new_jobs_count,
            "duplicates_removed": duplicates_removed,
            "errors": errors,
            "jobs": processed_jobs,
            "duplicate_records": duplicate_records_list
        }
