"""Configuration settings for IPO Tracker."""

import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""

    # Base directories
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)

    @property
    def DATA_DIR(self) -> Path:
        """Data directory path."""
        return self.BASE_DIR / "data"

    @property
    def RAW_DIR(self) -> Path:
        """Raw data directory path."""
        return self.DATA_DIR / "raw"

    @property
    def CACHE_DIR(self) -> Path:
        """HTTP response cache directory."""
        return self.DATA_DIR / "raw" / "cache"

    @property
    def EXPORT_DIR(self) -> Path:
        """Export directory path."""
        return self.DATA_DIR / "exports"

    @property
    def DB_PATH(self) -> Path:
        """Database file path."""
        return self.DATA_DIR / "ipo_tracker.db"

    @property
    def DATABASE_URL(self) -> str:
        """SQLAlchemy database URL."""
        return f"sqlite:///{self.DB_PATH}"

    # HTTP client
    HTTP_TIMEOUT: float = Field(default=30.0)
    HTTP_RATE_LIMIT_DELAY: float = Field(default=1.0)  # seconds between requests
    HTTP_MAX_RETRIES: int = Field(default=3)
    # SEC EDGAR requires a descriptive User-Agent; override via .env or env var
    SEC_USER_AGENT: str = Field(default="ipo-tracker research@example.com")

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()