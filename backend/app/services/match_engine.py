import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlmodel import Session, select
from pydantic import BaseModel, Field

from app.config import settings
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.match import MatchResult, RecommendationEnum
from app.services.llm_client import get_llm_client, BaseLLMClient
from app.services.normalization import JobNormalizationService

logger = logging.getLogger("jobhunter")

# ==========================================
# 1. LLM MATCH ANALYSIS SCHEMA
# ==========================================

class MatchAnalysisSchema(BaseModel):
    required_skills_identified: List[str] = Field(
        description="Required skills/technologies explicitly demanded in the job description."
    )
    preferred_skills_identified: List[str] = Field(
        description="Preferred or optional nice-to-have skills listed in the job description."
    )
    role_similarity: float = Field(
        description="Semantic similarity score between 0.0 and 1.0 of the candidate's roles to this job."
    )
    experience_interpretation: str = Field(
        description="Assessment of candidate's experience relevance and potential equivalencies."
    )
    qualification_interpretation: str = Field(
        description="Assessment of whether candidate's education matches or holds equivalent value."
    )
    concerns: List[str] = Field(
        description="Core concerns, missing required qualifications, or potential mismatches."
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0 of the LLM model on this matching."
    )
    reasoning_summary: str = Field(
        description="Short, bulleted explanation detailing why the candidate fits or doesn't fit."
    )


# ==========================================
# 2. STRING SIMILARITY UTILITIES (Pure Python)
# ==========================================

def get_levenshtein_ratio(s1: str, s2: str) -> float:
    """Calculates Levenshtein similarity ratio between two short strings."""
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
            cost = 0 if s1[row-1] == s2[col-1] else 1
            dist[row][col] = min(
                dist[row-1][col] + 1,      # deletion
                dist[row][col-1] + 1,      # insertion
                dist[row-1][col-1] + cost  # substitution
            )
            
    max_len = max(len(s1), len(s2))
    return 1.0 - (dist[rows-1][cols-1] / max_len)


# ==========================================
# 3. MATCH ENGINE SERVICE
# ==========================================

class MatchEngineService:
    """
    Hybrid scoring and suitability matching service for Candidate Profiles and Jobs.
    """
    
    MATCH_ENGINE_VERSION = "1.0"
    
    @staticmethod
    def calculate_candidate_experience_years(profile: CandidateProfile) -> float:
        """
        Sums candidate years of experience based on job records in Candidate Profile.
        """
        total_days = 0
        if not profile.experience:
            return 0.0
            
        for exp in profile.experience:
            try:
                start = datetime.strptime(exp.start_date, "%Y-%m-%d") if exp.start_date else datetime.utcnow()
                end = datetime.strptime(exp.end_date, "%Y-%m-%d") if exp.end_date else datetime.utcnow()
                total_days += (end - start).days
            except Exception:
                # Default fallback: assume 1 year of experience for entries with unparseable dates
                total_days += 365
                
        return max(0.0, total_days / 365.25)

    @classmethod
    def execute_deterministic_matching(
        cls, 
        profile: CandidateProfile, 
        job: Job
    ) -> Dict:
        """
        Performs 100-point deterministic match logic based on candidate preferences and normalized values.
        Splits:
          1. Skills: 35 points
          2. Experience: 20 points
          3. Role Title: 15 points
          4. Location & Remote: 15 points
          5. Education: 10 points
          6. Qualification Compliance: 5 points
        """
        # Load candidate normalized skills pool from database model columns
        candidate_skills = []
        for cat in [
            "skills_programming_languages", 
            "skills_frameworks", 
            "skills_libraries", 
            "skills_databases", 
            "skills_cloud", 
            "skills_tools", 
            "skills_others"
        ]:
            val = getattr(profile, cat, [])
            if val:
                candidate_skills.extend(val)
                
        candidate_skills_set = set(JobNormalizationService.normalize_skills(candidate_skills))
        job_skills_set = set(JobNormalizationService.normalize_skills(job.skills or []))
        
        # 1. Skills Score (35 pts)
        matching_skills = list(candidate_skills_set.intersection(job_skills_set))
        if job_skills_set:
            skill_ratio = len(matching_skills) / len(job_skills_set)
        else:
            skill_ratio = 1.0  # Default to full if no specific technologies listed
        skill_score = skill_ratio * 35.0
        
        missing_skills = list(job_skills_set.difference(candidate_skills_set))
        
        # 2. Experience Fit (20 pts)
        candidate_years = cls.calculate_candidate_experience_years(profile)
        experience_score = 20.0
        experience_gap = 0.0
        concerns = []
        
        required_exp = job.experience_required or 0.0
        if candidate_years < required_exp:
            experience_gap = required_exp - candidate_years
            # Deduct 4 points per year of experience gap
            experience_score = max(0.0, 20.0 - (experience_gap * 4.0))
            
        # Severe experience gating rule: Gaps >= 4 years cap overall score at 40
        has_severe_experience_gap = (required_exp >= 5.0 and candidate_years <= 1.0) or (experience_gap >= 4.0)
        if has_severe_experience_gap:
            concerns.append(f"Severe experience mismatch (Job requires {required_exp} years, candidate has {candidate_years:.1f} years). Score capped at 40.")
            
        # 3. Role Title Alignment (15 pts)
        role_score = 0.0
        preferred_roles = profile.preferred_roles or []
        job_title_norm = job.normalized_title or ""
        
        if not preferred_roles:
            role_score = 10.0  # Unspecified preferences gets a default baseline
        else:
            best_ratio = 0.0
            for pref in preferred_roles:
                pref_norm = JobNormalizationService.normalize_title(pref)
                # Check exact or edit distance overlap
                ratio = get_levenshtein_ratio(pref_norm, job_title_norm)
                if pref_norm in job_title_norm or job_title_norm in pref_norm:
                    ratio = max(ratio, 0.90)
                best_ratio = max(best_ratio, ratio)
                
            if best_ratio >= 0.85:
                role_score = 15.0
            elif best_ratio >= 0.50:
                role_score = 10.0
            else:
                role_score = 5.0
                
        # 4. Location & Remote Fit (15 pts)
        location_score = 15.0
        remote_pref = profile.remote_preference
        pref_locs = profile.preferred_locations or []
        job_loc_norm = job.normalized_location or ""
        job_remote = job.remote_status or "unspecified"
        
        # Check strict vs preferred vs unspecified remote alignment
        if remote_pref == "remote":
            if job_remote == "remote":
                location_score = 15.0
            elif job_remote == "hybrid":
                # Preferred remote candidate matching hybrid role: moderate penalty
                location_score = 8.0
                concerns.append("Candidate prefers Remote, but role is Hybrid.")
            else:
                # Onsite job is a strict remote mismatch: major penalty
                location_score = 0.0
                concerns.append("Strict Remote preference mismatch (Job is Onsite).")
        elif remote_pref == "onsite":
            if job_remote == "onsite":
                location_score = 15.0
            elif job_remote == "remote":
                location_score = 8.0
            else:
                location_score = 5.0
        elif remote_pref == "hybrid":
            if job_remote in ["hybrid", "remote"]:
                location_score = 15.0
            else:
                location_score = 6.0
                
        # Specific Location Check (if not unspecified)
        if pref_locs and job_remote != "remote":
            loc_matched = False
            for loc in pref_locs:
                norm_loc = loc.lower().strip()
                if norm_loc in job_loc_norm or job_loc_norm in norm_loc:
                    loc_matched = True
                    break
            if not loc_matched:
                location_score = max(0.0, location_score - 8.0)
                concerns.append(f"Location mismatch: Job is in '{job.location}', not in preferred targets: {pref_locs}.")
                
        # 5. Education Fit (10 pts)
        education_score = 10.0
        candidate_degrees = [edu.degree.lower() for edu in profile.education if edu.degree]
        
        # Simple heuristic check: if job description mentions "degree", "bachelor", "master", "phd"
        desc_lower = job.description.lower()
        requires_degree = any(term in desc_lower for term in ["degree", "bachelor", "bs", "ba", "ms", "master", "ph.d", "phd"])
        
        if requires_degree and not candidate_degrees:
            education_score = 0.0
            concerns.append("Job requires a degree, but candidate profile lists no completed education records.")
        elif requires_degree:
            # Check if degree fields align with technical roles
            is_tech_degree = any(
                any(term in field.field_of_study.lower() for term in ["computer", "software", "engineering", "information", "science", "math"])
                for field in profile.education if field.field_of_study
            )
            if not is_tech_degree:
                education_score = 5.0
                concerns.append("Candidate holds a non-technical degree matching technical role requirements.")
                
        # 6. Qualification Compliance (5 pts)
        # Penalizes missing required parameters rather than counting skills again
        compliance_score = 5.0
        # If any skills listed as required are missing, apply full compliance penalty
        required_keywords_in_job = [s for s in job.skills if s in desc_lower and "required" in desc_lower[max(0, desc_lower.find(s)-50):desc_lower.find(s)+50]]
        
        missing_required = [s for s in required_keywords_in_job if s not in candidate_skills_set]
        if missing_required:
            compliance_score = 0.0
            concerns.append(f"Missing required qualifications explicitly demanded: {missing_required[:3]}")
        elif missing_skills:
            # Deduct 1.0 point per missing preferred skill, capped at a minimum of 2.0 compliance points
            compliance_score = max(2.0, 5.0 - len(missing_skills) * 1.0)
            
        # Summarize deterministic overall score
        raw_overall = skill_score + experience_score + role_score + location_score + education_score + compliance_score
        overall_score = min(100.0, max(0.0, raw_overall))
        
        # Apply strict score cap if severe mismatch is flagged
        if has_severe_experience_gap:
            overall_score = min(overall_score, 40.0)
            
        return {
            "overall_score": round(overall_score, 1),
            "skill_score": round(skill_score, 1),
            "experience_score": round(experience_score, 1),
            "role_score": round(role_score, 1),
            "location_score": round(location_score, 1),
            "education_score": round(education_score, 1),
            "required_qualification_score": round(compliance_score, 1),
            "preferred_qualification_score": round(compliance_score, 1),
            "matching_skills": matching_skills,
            "missing_required_skills": missing_required,
            "missing_preferred_skills": [s for s in missing_skills if s not in missing_required],
            "experience_gap": round(experience_gap, 1),
            "concerns": concerns
        }

    @classmethod
    def check_ambiguity_triggers(
        cls, 
        profile: CandidateProfile, 
        job: Job, 
        deterministic_results: Dict
    ) -> bool:
        """
        Determines whether Gemini semantic analysis is required based on ambiguity signals.
        Returns True if ambiguous, False to skip and use deterministic fallback.
        """
        # Signal 1: Ambiguous role title alignment (fuzzy overlap, but not exact match)
        preferred_roles = profile.preferred_roles or []
        job_title_norm = job.normalized_title or ""
        best_ratio = 0.0
        for pref in preferred_roles:
            pref_norm = JobNormalizationService.normalize_title(pref)
            ratio = get_levenshtein_ratio(pref_norm, job_title_norm)
            best_ratio = max(best_ratio, ratio)
            
        is_title_ambiguous = (0.35 <= best_ratio <= 0.79)
        
        # Signal 2: Education field ambiguity (candidate has degree, but field study is equivalent/borderline)
        desc_lower = job.description.lower()
        requires_degree = any(term in desc_lower for term in ["degree", "bachelor", "bs", "master"])
        has_degree_but_non_tech = requires_degree and len(profile.education) > 0 and deterministic_results["education_score"] == 5.0
        
        # Signal 3: Ambiguous experience wording (job doesn't specify numeric experience but mentions terms)
        is_exp_wording_ambiguous = (job.experience_required is None) and any(term in desc_lower for term in ["industry experience", "equivalent background", "track record"])
        
        # Trigger if any of the above ambiguity conditions are satisfied
        if is_title_ambiguous or has_degree_but_non_tech or is_exp_wording_ambiguous:
            logger.info(f"Ambiguity detected: TitleSim={best_ratio:.2f}, NonTechDeg={has_degree_but_non_tech}, ExpWording={is_exp_wording_ambiguous}. Triggering Gemini analysis.")
            return True
            
        logger.info("Match criteria is clear-cut. Skipping Gemini invocation.")
        return False

    @classmethod
    async def match_job_suitability(
        cls, 
        profile: CandidateProfile, 
        job: Job, 
        session: Session,
        include_llm: bool = True
    ) -> MatchResult:
        """
        Performs hybrid matching. Uses deterministic checks, selectively triggers Gemini for ambiguity,
        and saves/updates result in database using candidate_profile_id + job_id unique constraints.
        """
        # 1. Run deterministic scoring
        det = cls.execute_deterministic_matching(profile, job)
        
        overall_score = det["overall_score"]
        matching_skills = det["matching_skills"]
        missing_required = det["missing_required_skills"]
        missing_preferred = det["missing_preferred_skills"]
        experience_gap = det["experience_gap"]
        concerns = det["concerns"]
        
        explanation_text = ""
        confidence = 1.0
        
        # 2. Check if we trigger LLM analysis
        enable_llm = include_llm and getattr(settings, "GEMINI_API_KEY", None) is not None
        trigger_gemini = enable_llm and cls.check_ambiguity_triggers(profile, job, det)
        
        if trigger_gemini:
            # 3. Safe Prompt Construction (Privacy focus: strip emails, phone numbers, complete names)
            # Create a minimized profile dictionary
            minimized_profile = {
                "skills": {
                    "programming_languages": profile.skills_programming_languages,
                    "frameworks": profile.skills_frameworks,
                    "databases": profile.skills_databases,
                    "cloud": profile.skills_cloud
                },
                "experience": [{"role": exp.role, "description": exp.description, "technologies": exp.technologies} for exp in profile.experience],
                "education": [{"degree": edu.degree, "field_of_study": edu.field_of_study} for edu in profile.education]
            }
            
            prompt = (
                f"Analyze suitability of candidate profile for job:\n\n"
                f"=== JOB ===\n"
                f"Title: {job.title}\n"
                f"Location: {job.location}\n"
                f"Remote: {job.remote_status}\n"
                f"Description: {job.description[:1500]}...\n\n"
                f"=== CANDIDATE PROFILE ===\n"
                f"Skills: {minimized_profile['skills']}\n"
                f"Experience: {minimized_profile['experience']}\n"
                f"Education: {minimized_profile['education']}\n\n"
                f"Determine if candidate's background holds equivalent required/preferred qualifications, "
                f"role similarity, and list specific gaps. Keep explanation concise."
            )
            
            try:
                import asyncio
                llm: BaseLLMClient = get_llm_client()
                # Run structured Gemini call with timeout safety
                response_data = await asyncio.wait_for(
                    llm.parse_structured(prompt, MatchAnalysisSchema),
                    timeout=10.0
                )
                
                # Semantic overrides
                confidence = response_data.confidence
                explanation_text = response_data.reasoning_summary
                
                # Append any semantic concerns identified by Gemini
                if response_data.concerns:
                    concerns.extend(response_data.concerns)
                    # Filter unique values
                    concerns = list(set(concerns))
                    
                # Role similarity adjustment (Semantic override on role_score)
                # Adjust role score based on Gemini semantic title evaluations
                semantic_role_score = response_data.role_similarity * 15.0
                det["role_score"] = round(semantic_role_score, 1)
                
                # Re-calculate overall score after semantic updates
                raw_score = (
                    det["skill_score"] + 
                    det["experience_score"] + 
                    det["role_score"] + 
                    det["location_score"] + 
                    det["education_score"] + 
                    det["required_qualification_score"]
                )
                overall_score = min(100.0, max(0.0, raw_score))
                
                # Check for experience gating cap
                if det["experience_gap"] >= 4.0 or (job.experience_required and job.experience_required >= 5.0 and cls.calculate_candidate_experience_years(profile) <= 1.0):
                    overall_score = min(overall_score, 40.0)
                    
            except Exception as e:
                logger.error(f"Gemini semantic analysis transaction failed or timed out: {e}. Falling back to deterministic results.")
                explanation_text = ""
                confidence = 0.5
                
        # 4. Construct explanation statement when Gemini is skipped or fails
        if not explanation_text:
            explanation_text = (
                f"Deterministic suitability analysis:\n"
                f"- Skills overlap: {len(matching_skills)} matches, {len(missing_preferred)} missing.\n"
                f"- Experience gap: {experience_gap:.1f} year(s).\n"
                f"- Location compatibility: {det['location_score']}/15.\n"
                f"- Role compatibility: {det['role_score']}/15."
            )
            
        # 5. Recommendation maps based on overall numeric score
        if overall_score >= 80.0:
            rec = RecommendationEnum.STRONG_MATCH
        elif overall_score >= 60.0:
            rec = RecommendationEnum.MATCH
        elif overall_score >= 45.0:
            rec = RecommendationEnum.POSSIBLE
        elif overall_score >= 30.0:
            rec = RecommendationEnum.WEAK_MATCH
        else:
            rec = RecommendationEnum.REJECT
            
        # 6. Database Upsert using candidate_profile_id + job_id unique indexes
        cand_id_str = str(profile.id) if profile.id is not None else "1"
        stmt = select(MatchResult).where(
            (MatchResult.candidate_profile_id == cand_id_str) &
            (MatchResult.job_id == job.job_id)
        )
        existing = session.exec(stmt).first()
        
        if existing:
            # Recalculate / Update matching details
            existing.overall_score = round(overall_score, 1)
            existing.recommendation = rec
            existing.skill_score = det["skill_score"]
            existing.experience_score = det["experience_score"]
            existing.education_score = det["education_score"]
            existing.role_score = det["role_score"]
            existing.location_score = det["location_score"]
            existing.required_qualification_score = det["required_qualification_score"]
            existing.preferred_qualification_score = det["preferred_qualification_score"]
            existing.matching_skills = matching_skills
            existing.missing_required_skills = missing_required
            existing.missing_preferred_skills = missing_preferred
            existing.experience_gap = det["experience_gap"]
            existing.concerns = concerns
            existing.explanation = explanation_text
            existing.confidence = confidence
            existing.engine_version = cls.MATCH_ENGINE_VERSION
            existing.updated_at = datetime.utcnow()
            
            session.add(existing)
            session.commit()
            session.refresh(existing)
            logger.info(f"Updated MatchResult for candidate '{profile.name}' and job '{job.title}'. Score: {existing.overall_score}%")
            return existing
        else:
            # Create a brand new matching row
            new_match = MatchResult(
                job_id=job.job_id,
                candidate_profile_id=cand_id_str,
                overall_score=round(overall_score, 1),
                recommendation=rec,
                skill_score=det["skill_score"],
                experience_score=det["experience_score"],
                education_score=det["education_score"],
                role_score=det["role_score"],
                location_score=det["location_score"],
                required_qualification_score=det["required_qualification_score"],
                preferred_qualification_score=det["preferred_qualification_score"],
                matching_skills=matching_skills,
                missing_required_skills=missing_required,
                missing_preferred_skills=missing_preferred,
                experience_gap=det["experience_gap"],
                concerns=concerns,
                explanation=explanation_text,
                confidence=confidence,
                engine_version=cls.MATCH_ENGINE_VERSION,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            session.add(new_match)
            session.commit()
            session.refresh(new_match)
            logger.info(f"Saved new MatchResult for candidate '{profile.name}' and job '{job.title}'. Score: {new_match.overall_score}%")
            return new_match

