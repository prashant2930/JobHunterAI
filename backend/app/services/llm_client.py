from abc import ABC, abstractmethod
from typing import Optional
import logging
import json

from app.models.candidate import (
    CandidateProfileSchema,
    PersonalInfoSchema,
    SkillsSchema,
    AdditionalInfoSchema,
    UserPreferencesSchema
)
from app.config import settings

logger = logging.getLogger("jobhunter")

class BaseLLMClient(ABC):
    """
    Provider-neutral interface for LLM operations.
    Business logic and resume parsing services depend ONLY on this abstraction.
    """
    
    @abstractmethod
    def parse_resume(self, resume_text: str) -> CandidateProfileSchema:
        """
        Parses raw resume text into a structured, schema-validated CandidateProfileSchema.
        Must NOT populate preferences (preferred_roles, preferred_locations, etc.).
        """
        pass

    @abstractmethod
    async def parse_structured(self, prompt: str, schema_class: type):
        """
        Executes a prompt against the LLM, expecting a response structured according to schema_class.
        """
        pass


class GeminiClient(BaseLLMClient):
    """
    Gemini implementation of BaseLLMClient using the google-genai SDK.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        try:
            from google import genai
            # Initialize GenAI Client using the SDK configuration
            self.client = genai.Client(api_key=self.api_key)
        except ImportError as e:
            logger.error("Failed to import 'google-genai' SDK in GeminiClient. Ensure it is installed in requirements.")
            raise e

    def parse_resume(self, resume_text: str) -> CandidateProfileSchema:
        from google.genai import types
        
        system_instruction = (
            "You are an expert resume parsing system. "
            "Your goal is to extract facts from the candidate's resume and return a structured JSON response. "
            "Follow these strict directives:\n"
            "1. Extract ONLY facts explicitly stated in the resume text. Do NOT invent, assume, or extrapolate skills, experience, projects, or dates.\n"
            "2. If an optional field or list is not present in the resume, return null or an empty list.\n"
            "3. Under 'preferences', do NOT attempt to guess or infer 'preferred_roles', 'preferred_locations', 'remote_preference', or 'experience_level'. "
            "These fields MUST remain completely empty (empty lists / null) in your output. They will be completed later by the user.\n"
            "4. Match the requested schema format exactly."
        )
        
        # We use gemini-2.5-flash for structured text tasks
        model_name = "gemini-2.5-flash"
        
        try:
            logger.info("Initiating Gemini structured content call for resume parsing...")
            
            # Request structured output matching CandidateProfileSchema
            response = self.client.models.generate_content(
                model=model_name,
                contents=f"Please parse this resume:\n\n{resume_text}",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=CandidateProfileSchema,
                    temperature=0.0,  # Zero-temperature for deterministic extraction
                ),
            )
            
            # Load the returned JSON string
            extracted_data = json.loads(response.text)
            
            # Safety Check: Enforce that preferences are NOT inferred by overriding them to default empty values
            extracted_data["preferences"] = {
                "preferred_roles": [],
                "preferred_locations": [],
                "remote_preference": None,
                "experience_level": None
            }
            
            # Explicitly label the source metadata
            extracted_data["profile_source"] = "extracted"
            extracted_data["preferences_source"] = "none"
            
            # Construct and validate using Pydantic schema
            profile = CandidateProfileSchema(**extracted_data)
            logger.info("Resume parsed and validated against CandidateProfileSchema successfully.")
            return profile
            
        except Exception as e:
            logger.error(f"Structured resume parsing failed in GeminiClient: {e}", exc_info=True)
            raise RuntimeError(f"Structured resume parsing failed: {e}")

    async def parse_structured(self, prompt: str, schema_class: type):
        from google.genai import types
        model_name = "gemini-2.5-flash"
        try:
            logger.info(f"Initiating Gemini structured content call for schema {schema_class.__name__}...")
            
            def run_sync_call():
                return self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema_class,
                        temperature=0.0,
                    ),
                )
            
            import asyncio
            response = await asyncio.to_thread(run_sync_call)
            extracted_data = json.loads(response.text)
            return schema_class(**extracted_data)
        except Exception as e:
            logger.error(f"Structured LLM parsing failed in GeminiClient for {schema_class.__name__}: {e}", exc_info=True)
            raise RuntimeError(f"Structured LLM parsing failed: {e}")


class FakeLLMClient(BaseLLMClient):
    """
    Fake implementation of BaseLLMClient for testing purposes.
    Avoids hitting the live Gemini API and does not require an API key.
    """
    
    def __init__(self, mock_response: Optional[CandidateProfileSchema] = None):
        self.mock_response = mock_response

    def parse_resume(self, resume_text: str) -> CandidateProfileSchema:
        if self.mock_response:
            return self.mock_response
            
        # Return a standard pre-populated mock profile
        return CandidateProfileSchema(
            version="1.0",
            personal_info=PersonalInfoSchema(
                name="John Doe",
                email="john.doe@example.com",
                phone="123-456-7890",
                location="Boston, MA"
            ),
            education=[],
            skills=SkillsSchema(
                programming_languages=["Python", "TypeScript", "SQL"],
                frameworks=["FastAPI", "React"],
                libraries=[],
                databases=["SQLite", "PostgreSQL"],
                cloud=[],
                tools=["Git", "Docker"],
                other_skills=[]
            ),
            experience=[],
            projects=[],
            certifications=[],
            additional_info=AdditionalInfoSchema(
                achievements=[],
                languages=[],
                links=[]
            ),
            preferences=UserPreferencesSchema(
                preferred_roles=[],
                preferred_locations=[],
                remote_preference=None,
                experience_level=None
            ),
            profile_source="extracted",
            preferences_source="none"
        )

    async def parse_structured(self, prompt: str, schema_class: type):
        if schema_class.__name__ == "MatchAnalysisSchema":
            return schema_class(
                required_skills_identified=["Python", "FastAPI"],
                preferred_skills_identified=["Docker"],
                role_similarity=0.9,
                experience_interpretation="Candidate has relevant experience.",
                qualification_interpretation="Candidate holds equivalent degrees.",
                concerns=[],
                confidence=1.0,
                reasoning_summary="Matching skills are strong. Location and remote preferences align."
            )
        try:
            return schema_class()
        except Exception:
            return schema_class.model_construct()


# ==========================================
# 3. CLIENT REGISTRY / INJECTION FACTORY
# ==========================================

_llm_client: Optional[BaseLLMClient] = None

def get_llm_client() -> BaseLLMClient:
    """
    Factory function to retrieve the active LLM client.
    Exposes the provider-neutral BaseLLMClient to business logic.
    """
    global _llm_client
    if _llm_client is not None:
        return _llm_client
        
    # Instantiate client depending on configurations
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
        logger.info("GEMINI_API_KEY detected. Initializing GeminiClient.")
        _llm_client = GeminiClient(api_key=settings.GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY is not set or placeholder. Falling back to FakeLLMClient.")
        _llm_client = FakeLLMClient()
        
    return _llm_client

def set_llm_client(client: BaseLLMClient):
    """
    Overrides the global LLM client (primarily for injection in test suites).
    """
    global _llm_client
    _llm_client = client
