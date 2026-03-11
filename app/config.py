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

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()