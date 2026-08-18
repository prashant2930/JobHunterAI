import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from app.scrapers.base import BaseJobSource

logger = logging.getLogger("jobhunter")

class RemotiveSource(BaseJobSource):
    """
    Search adapter for Remotive public API (https://remotive.com/api/remote-jobs).
    Requires no API key, providing real software and tech remote job feeds.
    """

    async def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        remote: Optional[str] = None,
        page: int = 1,
        limit: int = 10
    ) -> List[Dict]:

        if remote == "onsite":
            return []

        url = "https://remotive.com/api/remote-jobs"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        logger.info("Fetching Remotive public jobs feed...")

        max_retries = 2
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(max_retries):
                try:
                    search_url = f"{url}?search={query.strip()}" if query.strip() else url
                    response = await client.get(search_url, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                    raw_listings = data.get("jobs", [])
                    if not isinstance(raw_listings, list):
                        return []

                    keywords = [kw.lower().strip() for kw in query.split() if kw.strip()]
                    loc_filter = location.lower().strip() if location else None

                    filtered = []
                    for item in raw_listings:
                        job_loc = (item.get("candidate_required_location") or "").lower()
                        if loc_filter and loc_filter not in job_loc and "worldwide" not in job_loc and "anywhere" not in job_loc:
                            continue

                        title = item.get("title", "").lower()
                        company = item.get("company_name", "").lower()
                        category = item.get("category", "").lower()
                        desc = item.get("description", "").lower()
                        tags = [t.lower() for t in item.get("tags", [])]

                        match = False
                        if not keywords:
                            match = True
                        else:
                            for kw in keywords:
                                if kw in title or kw in company or kw in category or any(kw in tag for tag in tags):
                                    match = True
                                    break



                        if match:
                            filtered.append(item)

                    start_idx = (page - 1) * limit
                    end_idx = start_idx + limit
                    paginated = filtered[start_idx:end_idx]

                    jobs = []
                    for item in paginated:
                        skills = item.get("tags", [])
                        if item.get("category"):
                            skills.append(item["category"])

                        jobs.append({
                            "source": "remotive",
                            "source_job_id": str(item.get("id")),
                            "title": item.get("title", "Untitled"),
                            "company": item.get("company_name", "Unknown"),
                            "location": item.get("candidate_required_location") or "Remote",
                            "remote_status": "remote",
                            "description": item.get("description", ""),
                            "application_url": item.get("url", ""),
                            "posted_date": item.get("publication_date"),
                            "employment_type": item.get("job_type", "full-time"),
                            "skills": list(set(skills))
                        })

                    return jobs

                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Remotive search failed on attempt {attempt + 1}: {e}")
                        return []
                    await asyncio.sleep(1.0)

            return []
