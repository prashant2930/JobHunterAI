import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from app.scrapers.base import BaseJobSource

logger = logging.getLogger("jobhunter")

class RemoteOKSource(BaseJobSource):
    """
    Search adapter for RemoteOK (https://remoteok.com/api).
    Requires no API keys, providing real remote job feeds out of the box.
    """
    
    async def search_jobs(
        self, 
        query: str, 
        location: Optional[str] = None, 
        remote: Optional[str] = None, 
        page: int = 1, 
        limit: int = 10
    ) -> List[Dict]:
        
        # RemoteOK is strictly a remote board, skip if the user is looking only for onsite positions
        if remote == "onsite":
            return []
            
        url = "https://remoteok.com/api"
        
        # Web scraper safety: use a standard web browser user agent header
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        
        logger.info("Fetching RemoteOK public jobs feed...")
        
        max_retries = 3
        backoff_factor = 1.5
        timeout = httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=5.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    
                    # RemoteOK returns list: first item is a legal notice/disclaimer
                    if not isinstance(data, list) or len(data) <= 1:
                        logger.warning("RemoteOK returned an empty or invalid format list.")
                        return []
                        
                    raw_listings = data[1:]
                    
                    # Perform local filtering based on keywords (query strings)
                    keywords = [kw.lower().strip() for kw in query.split() if kw.strip()]
                    filtered_listings = []
                    
                    for item in raw_listings:
                        title = item.get("position", "").lower()
                        description = item.get("description", "").lower()
                        tags = [tag.lower() for tag in item.get("tags", [])]
                        
                        match = False
                        if not keywords:
                            match = True
                        else:
                            for kw in keywords:
                                if kw in title or any(kw in tag for tag in tags):
                                    match = True
                                    break

                                    
                        if match:
                            filtered_listings.append(item)
                    
                    # Apply local pagination slicing
                    start_index = (page - 1) * limit
                    end_index = start_index + limit
                    paginated_listings = filtered_listings[start_index:end_index]
                    
                    jobs = []
                    for item in paginated_listings:
                        jobs.append({
                            "source": "remoteok",
                            "source_job_id": str(item.get("id")),
                            "title": item.get("position"),
                            "company": item.get("company"),
                            "location": item.get("location") or "Remote",
                            "remote_status": "remote",
                            "description": item.get("description"),
                            "application_url": item.get("url"),
                            "salary_min": float(item.get("salary_min")) if item.get("salary_min") else None,
                            "salary_max": float(item.get("salary_max")) if item.get("salary_max") else None,
                            "salary_currency": "USD",  # RemoteOK defaults to USD
                            "posted_date": item.get("date"),
                            "employment_type": "full-time",
                            "skills": item.get("tags", [])
                        })
                    return jobs
                    
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt == max_retries - 1:
                        logger.error(f"RemoteOK query failed permanently on attempt {attempt + 1}: {e}")
                        raise RuntimeError(f"RemoteOK search failed: {e}") from e
                        
                    sleep_time = backoff_factor ** attempt
                    logger.warning(f"RemoteOK query attempt {attempt + 1} failed: {e}. Retrying in {sleep_time:.2f}s...")
                    await asyncio.sleep(sleep_time)
            
            return []

