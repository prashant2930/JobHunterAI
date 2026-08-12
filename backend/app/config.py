from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

# Resolve .env relative to this file (backend/app/config.py),
# going up two levels to reach the project root where .env lives.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    BACKEND_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite:///./jobhunter.db"
    GEMINI_API_KEY: Optional[str] = None
    ADZUNA_APP_ID: Optional[str] = None
    ADZUNA_APP_KEY: Optional[str] = None
    ADZUNA_COUNTRY: str = "us"
    LOG_LEVEL: str = "INFO"

settings = Settings()
