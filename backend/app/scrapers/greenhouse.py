import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from app.scrapers.base import BaseJobSource

logger = logging.getLogger("jobhunter")

PUBLIC_GREENHOUSE_BOARDS = ["gitlab", "cloudflare", "hashicorp", "airtable"]

class GreenhousePublicSource(BaseJobSource):
    """
    Search adapter for public Greenhouse job boards API (https://boards-api.greenhouse.io/v1/boards/{company}/jobs).
    Queries public technology company ATS boards without requiring private tokens.
    """

    async def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        remote: Optional[str] = None,
        page: int = 1,
        limit: int = 10
    ) -> List[Dict]:

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        logger.info("Fetching Greenhouse public job boards feed...")

        timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
        keywords = [kw.lower().strip() for kw in query.split() if kw.strip()]
        loc_filter = location.lower().strip() if location else None

        all_matching_jobs = []

        async with httpx.AsyncClient(timeout=timeout) as client:
            for board in PUBLIC_GREENHOUSE_BOARDS:
                try:
                    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
                    res = await client.get(url, headers=headers)
                    if res.status_code != 200:
                        continue
                    data = res.json()
                    raw_jobs = data.get("jobs", [])

                    for item in raw_jobs:
                        title = (item.get("title") or "").lower()
                        loc_name = (item.get("location", {}).get("name") or "").lower()
                        is_remote = "remote" in loc_name or "anywhere" in loc_name or "virtual" in loc_name

                        if remote == "onsite" and is_remote:
                            continue
                        if remote == "remote" and not is_remote:
                            continue

                        if loc_filter and loc_filter not in loc_name and not (loc_filter in "remote" and is_remote):
                            continue

                        match = False
                        if not keywords:
                            match = True
                        else:
                            for kw in keywords:
                                if kw in title or kw in loc_name:
                                    match = True
                                    break

                        if match:
                            all_matching_jobs.append({
                                "source": "greenhouse",
                                "source_job_id": str(item.get("id")),
                                "title": item.get("title", "Untitled"),
                                "company": board.capitalize(),
                                "location": item.get("location", {}).get("name") or "Remote",
                                "remote_status": "remote" if is_remote else "onsite",
                                "description": f"{item.get('title')} at {board.capitalize()}",
                                "application_url": item.get("absolute_url") or f"https://boards.greenhouse.io/{board}/jobs/{item.get('id')}",
                                "posted_date": item.get("updated_at"),
                                "employment_type": "full-time",
                                "skills": [board.capitalize()]
                            })
                except Exception as e:
                    logger.warning(f"Greenhouse board '{board}' query skipped: {e}")
                    continue

        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        return all_matching_jobs[start_idx:end_idx]
