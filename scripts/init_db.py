#!/usr/bin/env python3
"""Database initialization script for IPO Tracker."""

import sys
import os
from pathlib import Path

# Add the parent directory to the Python path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.db import create_tables
from app.utils.logging import get_logger
from app.models import *  # Import all models to ensure they are registered


def create_directories():
    """Create necessary directories."""
    directories = [
        settings.DATA_DIR,
        settings.RAW_DIR,
        settings.EXPORT_DIR,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {directory}")


def init_database():
    """Initialize the database."""
    logger.info(f"Initializing database at: {settings.DB_PATH}")

    # Create the database directory if it doesn't exist
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Create all tables
    create_tables()
    logger.info("Database tables created successfully")


def main():
    """Main function."""
    logger.info("Starting database initialization...")

    try:
        # Create directories
        create_directories()

        # Initialize database
        init_database()

        logger.info("Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    logger = get_logger(__name__)
    main()