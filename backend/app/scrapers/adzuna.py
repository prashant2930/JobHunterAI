import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from app.config import settings
from app.scrapers.base import BaseJobSource

logger = logging.getLogger("jobhunter")

class AdzunaSource(BaseJobSource):
    """
    Search adapter for the Adzuna API.
    Requires ADZUNA_APP_ID and ADZUNA_APP_KEY to be configured in .env.
    """
    
    def __init__(self):
        self.app_id = getattr(settings, "ADZUNA_APP_ID", None)
        self.app_key = getattr(settings, "ADZUNA_APP_KEY", None)
        self.country = getattr(settings, "ADZUNA_COUNTRY", "us")

    async def search_jobs(
        self, 
        query: str, 
        location: Optional[str] = None, 
        remote: Optional[str] = None, 
        page: int = 1, 
        limit: int = 10
    ) -> List[Dict]:
        
        # Guard: Check for empty/placeholder credentials
        if not self.app_id or not self.app_key or self.app_id in ["", "your_adzuna_app_id_here"]:
            logger.warning("Adzuna API credentials are not set in .env. Skipping Adzuna source.")
            # Return empty list, other sources (RemoteOK) can still process
            return []
            
        url = f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/{page}"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": limit,
            "what": query,
        }
        
        if location:
            params["where"] = location
            
        # Adzuna does not have a direct query remote toggle, but we can append to the search term
        if remote == "remote":
            params["what"] = f"{query} remote"
            
        logger.info(f"Querying Adzuna API page {page} for query='{query}'...")
        
        max_retries = 3
        backoff_factor = 1.5
        timeout = httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=5.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.get(url, params=params)
                    
                    # Check for unauthorized credentials immediately (don't retry auth errors)
                    if response.status_code in [401, 403]:
                        logger.error("Adzuna credentials rejected. Check your ADZUNA_APP_ID and APP_KEY.")
                        raise ValueError("Adzuna API credentials rejected.")
                        
                    response.raise_for_status()
                    data = response.json()
                    results = data.get("results", [])
                    
                    jobs = []
                    for item in results:
                        # Format location area levels
                        loc_parts = item.get("location", {}).get("area", [])
                        loc_str = ", ".join(loc_parts) if loc_parts else item.get("location", {}).get("display_name", "Unknown")
                        
                        # Guess remote status based on title/description context
                        is_remote = "remote" in item.get("title", "").lower() or "remote" in item.get("description", "").lower()
                        remote_status = "remote" if is_remote else "unspecified"
                        
                        jobs.append({
                            "source": "adzuna",
                            "source_job_id": str(item.get("id")),
                            "title": item.get("title"),
                            "company": item.get("company", {}).get("display_name"),
                            "location": loc_str,
                            "remote_status": remote_status,
                            "description": item.get("description"),
                            "application_url": item.get("redirect_url"),
                            "salary_min": item.get("salary_min"),
                            "salary_max": item.get("salary_max"),
                            "posted_date": item.get("created"),
                            "employment_type": "full-time" if item.get("contract_type") == "full-time" else "unspecified"
                        })
                    return jobs
                    
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    # Raise immediately if it is a credential error or if we have run out of retries
                    if isinstance(e, ValueError) or attempt == max_retries - 1:
                        logger.error(f"Adzuna query failed permanently on attempt {attempt + 1}: {e}")
                        raise RuntimeError(f"Adzuna search failed: {e}") from e
                        
                    sleep_time = backoff_factor ** attempt
                    logger.warning(f"Adzuna query attempt {attempt + 1} failed: {e}. Retrying in {sleep_time:.2f}s...")
                    await asyncio.sleep(sleep_time)
            
            return []

