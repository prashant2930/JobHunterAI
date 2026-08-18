from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.application import Application, ApplicationFormField, QuestionAnswerSchema
from app.services.application_adapters import GenericApplicationAdapter
from app.services.llm_client import get_llm_client
from app.config import settings

logger = logging.getLogger("jobhunter")


class ApplicationAnalyzerService:
    """
    Service responsible for analyzing job application form fields, mapping candidate profile data,
    generating AI-assisted answers for subjective questions without hallucinating candidate facts,
    and enforcing human review requirements.
    """

    @classmethod
    async def analyze_job_application(
        cls,
        job: Job,
        profile: CandidateProfile,
        session: Session,
        application_url: Optional[str] = None,
        html_content: Optional[str] = None
    ) -> Application:

        url = application_url or job.application_url or ""
        platform = cls._detect_platform(url)

        # 1. Check if application record already exists for this job & profile
        stmt = select(Application).where(
            (Application.job_id == job.job_id) &
            (Application.candidate_profile_id == str(profile.id))
        )
        existing_app = session.exec(stmt).first()

        if existing_app:
            application = existing_app
            application.application_url = url
            application.platform = platform
            application.updated_at = datetime.utcnow()
            # Clear existing fields for re-analysis
            for f in list(application.fields):
                session.delete(f)
            session.commit()
            session.refresh(application)
        else:
            application = Application(
                job_id=job.job_id,
                candidate_profile_id=str(profile.id),
                application_url=url,
                platform=platform,
                status="READY_FOR_REVIEW"
            )
            session.add(application)
            session.commit()
            session.refresh(application)

        # 2. Extract form fields via GenericApplicationAdapter
        adapter = GenericApplicationAdapter()
        raw_fields = adapter.extract_fields(html_content or "")

        # 3. Process and map fields to profile facts and Gemini LLM where required
        fields_to_add: List[ApplicationFormField] = []

        for f_data in raw_fields:
            field_name = f_data["field_name"]
            label = f_data["label"]
            field_type = f_data["field_type"]
            required = f_data["required"]
            options = f_data.get("options", [])

            mapped_result = await cls._map_field(
                field_name=field_name,
                label=label,
                field_type=field_type,
                options=options,
                profile=profile,
                job=job
            )

            form_field = ApplicationFormField(
                application_id=application.id,
                field_name=field_name,
                label=label,
                field_type=field_type,
                required=required,
                options=options,
                current_value=mapped_result["suggested_value"],
                suggested_value=mapped_result["suggested_value"],
                source=mapped_result["source"],
                confidence=mapped_result["confidence"],
                requires_review=mapped_result["requires_review"]
            )
            fields_to_add.append(form_field)

        session.add_all(fields_to_add)
        session.commit()
        session.refresh(application)

        # Eager load fields for response serialization
        stmt_fields = select(ApplicationFormField).where(ApplicationFormField.application_id == application.id)
        application.fields = list(session.exec(stmt_fields).all())

        return application


    @classmethod
    def _detect_platform(cls, url: str) -> str:
        url_lower = url.lower()
        if "greenhouse.io" in url_lower:
            return "greenhouse"
        elif "lever.co" in url_lower:
            return "lever"
        elif "workday.com" in url_lower or "myworkdayjobs.com" in url_lower:
            return "workday"
        return "generic"

    @classmethod
    async def _map_field(
        cls,
        field_name: str,
        label: str,
        field_type: str,
        options: List[str],
        profile: CandidateProfile,
        job: Job
    ) -> Dict[str, Any]:
        norm_label = (label + " " + field_name).lower()
        name_parts = profile.name.strip().split() if profile.name else ["", ""]
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        # --- 1. Deterministic Profile Mappings ---
        if any(k in norm_label for k in ["first_name", "first name", "given name"]):
            return {"suggested_value": first_name, "source": "candidate_profile", "confidence": 1.0, "requires_review": False}

        if any(k in norm_label for k in ["last_name", "last name", "surname", "family name"]):
            return {"suggested_value": last_name, "source": "candidate_profile", "confidence": 1.0, "requires_review": False}

        if any(k in norm_label for k in ["full name", "full_name", "your name"]) or (norm_label == "name"):
            return {"suggested_value": profile.name, "source": "candidate_profile", "confidence": 1.0, "requires_review": False}

        if "email" in norm_label:
            return {"suggested_value": profile.email or "", "source": "candidate_profile", "confidence": 1.0, "requires_review": False}

        if any(k in norm_label for k in ["phone", "mobile", "contact number"]):
            return {"suggested_value": profile.phone or "", "source": "candidate_profile", "confidence": 1.0, "requires_review": False}

        if any(k in norm_label for k in ["location", "city", "address"]):
            return {"suggested_value": profile.location or "", "source": "candidate_profile", "confidence": 1.0, "requires_review": False}

        if "linkedin" in norm_label:
            linkedin_url = next((link for link in profile.links if "linkedin" in link.lower()), "")
            return {"suggested_value": linkedin_url, "source": "candidate_profile" if linkedin_url else "unknown", "confidence": 1.0 if linkedin_url else 0.0, "requires_review": not bool(linkedin_url)}

        if any(k in norm_label for k in ["github", "portfolio", "website", "url"]):
            url_match = next((link for link in profile.links if "github" in link.lower() or "http" in link.lower()), "")
            return {"suggested_value": url_match, "source": "candidate_profile" if url_match else "unknown", "confidence": 1.0 if url_match else 0.0, "requires_review": not bool(url_match)}

        if any(k in norm_label for k in ["resume", "cv", "attach"]):
            return {"suggested_value": "[Resume Attached]", "source": "candidate_profile", "confidence": 1.0, "requires_review": False}

        # --- 2. Subjective / Open-ended Questions (Gemini LLM) ---
        if any(k in norm_label for k in ["why do you want", "why work here", "cover letter", "describe a project", "motivation", "interest in role"]):
            llm_result = await cls._generate_llm_answer(label, profile, job)
            return llm_result

        # --- 3. Unknown / Factual / Legal questions not in profile ---
        # Never fabricate work authorization, salary expectations, or legal declarations!
        return {
            "suggested_value": None,
            "source": "unknown",
            "confidence": 0.0,
            "requires_review": True
        }

    @classmethod
    async def _generate_llm_answer(
        cls,
        question_label: str,
        profile: CandidateProfile,
        job: Job
    ) -> Dict[str, Any]:
        """
        Generates an AI response grounded strictly in candidate profile facts and job description.
        Never invents experience or facts not in the profile.
        """
        # If Gemini is not configured, return un-answered requiring review
        if not getattr(settings, "GEMINI_API_KEY", None) or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
            return {
                "suggested_value": None,
                "source": "unknown",
                "confidence": 0.0,
                "requires_review": True
            }

        try:
            llm = get_llm_client()
            skills_str = ", ".join(profile.skills_programming_languages + profile.skills_frameworks + profile.skills_tools)
            exp_summary = "; ".join([f"{e.role} at {e.company}" for e in profile.experience])

            prompt = (
                f"Question from job application: '{question_label}'\n\n"
                f"Target Job: {job.title} at {job.company}\n"
                f"Job Description: {job.description[:1000]}\n\n"
                f"Candidate Facts:\n"
                f"- Name: {profile.name}\n"
                f"- Location: {profile.location}\n"
                f"- Skills: {skills_str}\n"
                f"- Work History: {exp_summary}\n\n"
                f"Strict Safety & Truthfulness Rules:\n"
                f"1. Generate a concise, professional answer (2-4 sentences).\n"
                f"2. Use ONLY facts explicitly provided above. Do NOT invent job titles, companies, years of experience, or skills.\n"
                f"3. Return JSON conforming to QuestionAnswerSchema with fields: suggested_answer, confidence (0.0 to 1.0), requires_review (always True), reasoning."
            )

            res = await llm.parse_structured(prompt, QuestionAnswerSchema)
            return {
                "suggested_value": res.suggested_answer,
                "source": "llm_generated",
                "confidence": min(res.confidence, 0.85),
                "requires_review": True  # All AI-generated answers require human review
            }
        except Exception as e:
            logger.warning(f"LLM question generation failed: {e}. Marking for manual review.")
            return {
                "suggested_value": None,
                "source": "unknown",
                "confidence": 0.0,
                "requires_review": True
            }
