import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from app.scrapers.base import BaseJobSource

logger = logging.getLogger("jobhunter")

class JobicySource(BaseJobSource):
    """
    Search adapter for Jobicy public API (https://jobicy.com/api/v2/remote-jobs).
    Provides real tech/engineering public job feeds.
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

        url = f"https://jobicy.com/api/v2/remote-jobs?count=50"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        logger.info("Fetching Jobicy public jobs feed...")

        max_retries = 2
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                    raw_listings = data.get("jobs", [])
                    if not isinstance(raw_listings, list):
                        return []

                    keywords = [kw.lower().strip() for kw in query.split() if kw.strip()]
                    loc_filter = location.lower().strip() if location else None

                    filtered = []
                    for item in raw_listings:
                        job_geo = str(item.get("jobGeo") or "").lower()
                        if loc_filter and loc_filter not in job_geo and "anywhere" not in job_geo and "worldwide" not in job_geo:
                            continue

                        title = str(item.get("jobTitle") or "").lower()
                        company = str(item.get("companyName") or "").lower()
                        industry = str(item.get("jobIndustry") or "").lower()
                        desc = str(item.get("jobDescription") or item.get("jobExcerpt") or "").lower()


                        match = False
                        if not keywords:
                            match = True
                        else:
                            for kw in keywords:
                                if kw in title or kw in company or kw in industry:
                                    match = True
                                    break



                        if match:
                            filtered.append(item)

                    start_idx = (page - 1) * limit
                    end_idx = start_idx + limit
                    paginated = filtered[start_idx:end_idx]

                    jobs = []
                    for item in paginated:
                        skills = []
                        if item.get("jobIndustry"):
                            skills.append(item["jobIndustry"])
                        if item.get("jobLevel"):
                            skills.append(item["jobLevel"])

                        s_min = float(item["salaryMin"]) if item.get("salaryMin") and str(item["salaryMin"]).isdigit() else None
                        s_max = float(item["salaryMax"]) if item.get("salaryMax") and str(item["salaryMax"]).isdigit() else None

                        emp_type = item.get("jobType")
                        if isinstance(emp_type, list):
                            emp_type = ", ".join(emp_type)

                        jobs.append({
                            "source": "jobicy",
                            "source_job_id": str(item.get("id")),
                            "title": item.get("jobTitle", "Untitled"),
                            "company": item.get("companyName", "Unknown"),
                            "location": item.get("jobGeo") or "Remote",
                            "remote_status": "remote",
                            "description": item.get("jobDescription") or item.get("jobExcerpt") or "",
                            "application_url": item.get("url", ""),
                            "salary_min": s_min,
                            "salary_max": s_max,
                            "salary_currency": item.get("salaryCurrency") or "USD",
                            "posted_date": item.get("pubDate"),
                            "employment_type": emp_type or "full-time",
                            "skills": skills
                        })

                    return jobs

                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Jobicy search failed on attempt {attempt + 1}: {e}")
                        return []
                    await asyncio.sleep(1.0)

            return []
