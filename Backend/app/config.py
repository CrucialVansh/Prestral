from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mistral_api_key: str = Field(..., description="Mistral API key")
    mistral_chat_model: str = "mistral-large-latest"
    mistral_embed_model: str = "mistral-embed"
    chunk_max_chars: int = 1000
    chunk_overlap: int = 150
    top_k: int = 4

    # Google Drive OAuth (optional — only required for cloud import)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/storage/google/callback"
    drive_max_auto_docs: int = 3
    drive_preview_chars: int = 2500

    # Production: directory with Vite ``dist`` (index.html + assets). Empty = API only.
    static_dir: str = ""

    # Optional LibreOffice for slide PNGs (see slide_rasterizer).
    libreoffice_path: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
