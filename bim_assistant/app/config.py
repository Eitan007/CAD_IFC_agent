"""
app/config.py
Centralised settings loaded from .env via pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-4-5"

    # Database
    db_backend: str = "postgres"
    postgres_url: str = "postgresql+asyncpg://bim:bim_secret@localhost:5432/bim_db"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "bim_secret"

    # Storage paths
    upload_dir: str = "./data/uploads"
    processed_dir: str = "./data/processed"

    # RAG
    enable_rag: bool = False
    chroma_persist_dir: str = "./data/chroma"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str = "change_me_in_production"

    # LiveKit (voice sessions)
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
