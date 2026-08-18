import httpx
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from app.scrapers.base import BaseJobSource

logger = logging.getLogger("jobhunter")

class ArbeitnowSource(BaseJobSource):
    """
    Search adapter for Arbeitnow public job board API (https://www.arbeitnow.com/api/job-board-api).
    Requires no API keys, providing real public job listings.
    """

    async def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        remote: Optional[str] = None,
        page: int = 1,
        limit: int = 10
    ) -> List[Dict]:

        url = "https://www.arbeitnow.com/api/job-board-api"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        logger.info("Fetching Arbeitnow public jobs feed...")

        max_retries = 2
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.get(f"{url}?page={page}", headers=headers)
                    response.raise_for_status()
                    data = response.json()

                    raw_listings = data.get("data", [])
                    if not isinstance(raw_listings, list):
                        return []

                    keywords = [kw.lower().strip() for kw in query.split() if kw.strip()]
                    loc_filter = location.lower().strip() if location else None

                    filtered = []
                    for item in raw_listings:
                        is_remote = bool(item.get("remote"))
                        if remote == "onsite" and is_remote:
                            continue
                        if remote == "remote" and not is_remote:
                            continue

                        job_loc = (item.get("location") or "").lower()
                        if loc_filter and loc_filter not in job_loc and not (loc_filter in "remote" and is_remote):
                            continue

                        title = item.get("title", "").lower()
                        desc = item.get("description", "").lower()
                        company = item.get("company_name", "").lower()
                        tags = [t.lower() for t in item.get("tags", [])]

                        match = False
                        if not keywords:
                            match = True
                        else:
                            for kw in keywords:
                                if kw in title or kw in company or any(kw in tag for tag in tags):
                                    match = True
                                    break



                        if match:
                            filtered.append(item)

                    paginated = filtered[:limit]

                    jobs = []
                    for item in paginated:
                        created_ts = item.get("created_at")
                        posted_str = None
                        if created_ts:
                            try:
                                posted_str = datetime.utcfromtimestamp(created_ts).isoformat()
                            except Exception:
                                pass

                        jobs.append({
                            "source": "arbeitnow",
                            "source_job_id": item.get("slug", ""),
                            "title": item.get("title", "Untitled"),
                            "company": item.get("company_name", "Unknown"),
                            "location": item.get("location") or ("Remote" if item.get("remote") else "Unspecified"),
                            "remote_status": "remote" if item.get("remote") else "onsite",
                            "description": item.get("description", ""),
                            "application_url": item.get("url", ""),
                            "posted_date": posted_str,
                            "employment_type": ", ".join(item.get("job_types", [])) if item.get("job_types") else "full-time",
                            "skills": item.get("tags", [])
                        })

                    return jobs

                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Arbeitnow search failed on attempt {attempt + 1}: {e}")
                        return []
                    await asyncio.sleep(1.0)

            return []
