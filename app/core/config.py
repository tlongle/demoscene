"""
Configuration settings for DEMOSCENE.
Centralizes environment variables, port bindings, and storage paths.
"""
import os
from pathlib import Path


class Settings:
    # Server & Port Configuration (Default forward port: 5363)
    PORT: int = int(os.environ.get("PORT", 5363))
    HOST: str = os.environ.get("HOST", "0.0.0.0")

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    
    # SQLite Database Path
    DB_PATH: str = os.environ.get("DEMOPALS_DB_PATH", str(BASE_DIR / "data" / "demopals.db"))
    
    # Asset Storage Paths
    ASSETS_DIR: str = os.environ.get("ASSETS_DIR", str(BASE_DIR / "data" / "assets"))
    DEMOPALS_ASSETS_DIR: str = os.path.join(ASSETS_DIR, "demopals")
    BOXART_ASSETS_DIR: str = os.path.join(ASSETS_DIR, "boxart")
    
    # Static Web Files Path
    STATIC_DIR: str = str(BASE_DIR / "static")

    # IGDB / Twitch API Credentials
    @property
    def TWITCH_CLIENT_ID(self) -> str:
        return os.environ.get("TWITCH_CLIENT_ID", "").strip()

    @property
    def TWITCH_CLIENT_SECRET(self) -> str:
        return os.environ.get("TWITCH_CLIENT_SECRET", "").strip()

    def ensure_dirs(self) -> None:
        """Ensure all required data and asset storage directories exist."""
        db_parent = os.path.dirname(os.path.abspath(self.DB_PATH))
        if db_parent:
            os.makedirs(db_parent, exist_ok=True)
        os.makedirs(self.ASSETS_DIR, exist_ok=True)
        os.makedirs(self.DEMOPALS_ASSETS_DIR, exist_ok=True)
        os.makedirs(self.BOXART_ASSETS_DIR, exist_ok=True)
        os.makedirs(self.STATIC_DIR, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
