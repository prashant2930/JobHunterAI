import httpx
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from app.scrapers.base import BaseJobSource

logger = logging.getLogger("jobhunter")

PUBLIC_LEVER_BOARDS = ["docker", "sentry", "elastic", "affirm"]

class LeverPublicSource(BaseJobSource):
    """
    Search adapter for public Lever job boards API (https://api.lever.co/v0/postings/{company}).
    Queries public tech company ATS boards without requiring private API tokens.
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

        logger.info("Fetching Lever public job boards feed...")

        timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
        keywords = [kw.lower().strip() for kw in query.split() if kw.strip()]
        loc_filter = location.lower().strip() if location else None

        all_matching_jobs = []

        async with httpx.AsyncClient(timeout=timeout) as client:
            for board in PUBLIC_LEVER_BOARDS:
                try:
                    url = f"https://api.lever.co/v0/postings/{board}"
                    res = await client.get(url, headers=headers)
                    if res.status_code != 200:
                        continue
                    raw_jobs = res.json()
                    if not isinstance(raw_jobs, list):
                        continue

                    for item in raw_jobs:
                        title = str(item.get("text") or "").lower()
                        categories = item.get("categories") or {}
                        loc_name = str(categories.get("location") or "").lower()
                        workplace_type = str(item.get("workplaceType") or "").lower()
                        is_remote = "remote" in workplace_type or "remote" in loc_name or "anywhere" in loc_name

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
                                if kw in title or kw in loc_name or kw in str(categories.get("team") or "").lower():
                                    match = True
                                    break

                        if match:
                            created_at = item.get("createdAt")
                            posted_str = None
                            if created_at:
                                try:
                                    posted_str = datetime.utcfromtimestamp(created_at / 1000.0).isoformat()
                                except Exception:
                                    pass

                            all_matching_jobs.append({
                                "source": "lever",
                                "source_job_id": str(item.get("id")),
                                "title": item.get("text", "Untitled"),
                                "company": board.capitalize(),
                                "location": categories.get("location") or ("Remote" if is_remote else "Unspecified"),
                                "remote_status": "remote" if is_remote else "onsite",
                                "description": item.get("descriptionPlain") or item.get("text") or "",
                                "application_url": item.get("hostedUrl") or item.get("applyUrl") or f"https://jobs.lever.co/{board}/{item.get('id')}",
                                "posted_date": posted_str,
                                "employment_type": categories.get("commitment") or "full-time",
                                "skills": [board.capitalize(), categories.get("team")] if categories.get("team") else [board.capitalize()]
                            })
                except Exception as e:
                    logger.warning(f"Lever board '{board}' query skipped: {e}")
                    continue

        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        return all_matching_jobs[start_idx:end_idx]
