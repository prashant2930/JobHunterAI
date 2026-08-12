import logging
from typing import Tuple, Dict
from app.models.job import Job

logger = logging.getLogger("jobhunter")

def levenshtein_ratio(s1: str, s2: str) -> float:
    """
    Calculates the Levenshtein distance similarity ratio between two short strings.
    O(N*M) complexity - suited for titles and company names.
    """
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
        
    rows = len(s1) + 1
    cols = len(s2) + 1
    dist = [[0 for _ in range(cols)] for _ in range(rows)]
    
    for i in range(1, rows):
        dist[i][0] = i
    for j in range(1, cols):
        dist[0][j] = j
        
    for col in range(1, cols):
        for row in range(1, rows):
            if s1[row-1] == s2[col-1]:
                cost = 0
            else:
                cost = 1
            dist[row][col] = min(
                dist[row-1][col] + 1,      # deletion
                dist[row][col-1] + 1,      # insertion
                dist[row-1][col-1] + cost  # substitution
            )
            
    max_len = max(len(s1), len(s2))
    return 1.0 - (dist[rows-1][cols-1] / max_len)


def token_similarity(s1: str, s2: str) -> float:
    """
    Calculates Jaccard similarity of word tokens.
    O(N) complexity - suited for long descriptions.
    """
    if not s1 or not s2:
        return 0.0
    
    # Remove HTML tags and noise
    s1_clean = re_clean_tokens(s1)
    s2_clean = re_clean_tokens(s2)
    
    if not s1_clean or not s2_clean:
        return 0.0
        
    intersection = s1_clean.intersection(s2_clean)
    union = s1_clean.union(s2_clean)
    return len(intersection) / len(union)


def re_clean_tokens(text: str) -> set:
    import re
    # Strip HTML and extract alphanumeric lowercase words
    text_clean = re.sub(r'<[^>]*>', ' ', text.lower())
    words = re.findall(r'\b\w+\b', text_clean)
    return set(words)


class JobDeduplicationService:
    """
    Handles conservative job deduplication to prevent merging separate job listings.
    """
    
    @classmethod
    def check_duplicate(cls, job: Job, existing: Job) -> Tuple[bool, str]:
        """
        Compares an incoming job against an existing database job.
        Returns:
            (is_duplicate: bool, reason: str)
        """
        # ==========================================
        # LEVEL 1: Strict Identifiers
        # ==========================================
        if job.application_url and job.application_url == existing.application_url:
            return True, "duplicate_application_url"
            
        if (job.source == existing.source and 
            job.source_job_id == existing.source_job_id):
            return True, "duplicate_source_job_id"

        # ==========================================
        # LEVEL 2: Normalized Match with Supporting Similarity
        # ==========================================
        # Deduplication must be conservative. Require same company AND location.
        if (job.normalized_company == existing.normalized_company and 
            job.normalized_location == existing.normalized_location):
            
            # Case 2A: Same title spelling (e.g. "Software Engineer")
            if job.normalized_title == existing.normalized_title:
                # Companies list multiple separate slots with the exact same title.
                # We require description overlap (>80%) to verify they represent the same opening.
                desc_sim = token_similarity(job.description, existing.description)
                if desc_sim > 0.80:
                    return True, "duplicate_exact_company_title_location"
                else:
                    logger.info(
                        f"Detected separate listings at '{job.company}' with title '{job.title}' "
                        f"in '{job.location}' (description similarity: {desc_sim:.2f}). Preserving both."
                    )
            
            # Case 2B: Minor variations in title (e.g. "Software Engineer" vs "Software Developer")
            else:
                title_sim = levenshtein_ratio(job.normalized_title, existing.normalized_title)
                if title_sim > 0.85:
                    # Require extremely high description overlap (>90%) to merge close titles
                    desc_sim = token_similarity(job.description, existing.description)
                    if desc_sim > 0.90:
                        return True, "duplicate_fuzzy_identity"
                        
        return False, ""
