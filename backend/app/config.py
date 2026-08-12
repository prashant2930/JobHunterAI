from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
