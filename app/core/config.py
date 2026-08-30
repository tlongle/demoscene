"""
Configuration settings for DEMOSCENE.
Centralizes environment variables, port bindings, and storage paths.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()


class Settings:
    # Server & Port Configuration (Default forward port: 5363)
    PORT: int = int(os.environ.get("PORT", 5363))
    HOST: str = os.environ.get("HOST", "0.0.0.0")

    # Security & Access Control
    ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "").strip()
    CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "*").strip()

    # Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DB_PATH: str = os.environ.get("DEMOPALS_DB_PATH", str(BASE_DIR / "data" / "demopals.db"))
    ASSETS_DIR: str = os.environ.get("ASSETS_DIR", str(BASE_DIR / "data" / "assets"))
    DEMOPALS_ASSETS_DIR: str = str(Path(ASSETS_DIR) / "demopals")
    BOXART_ASSETS_DIR: str = str(Path(ASSETS_DIR) / "boxart")
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
        for path in (Path(self.DB_PATH).parent, Path(self.DEMOPALS_ASSETS_DIR), Path(self.BOXART_ASSETS_DIR), Path(self.STATIC_DIR)):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
