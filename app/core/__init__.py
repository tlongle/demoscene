"""
Core application configuration and database modules.
"""
from app.core.config import settings
import app.core.database as db

__all__ = ["settings", "db"]
