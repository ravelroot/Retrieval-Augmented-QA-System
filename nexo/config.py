from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEXO_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = Path("data")
    database_url: str | None = None
    secret: str | None = None
    token_hours: int = Field(8, ge=1, le=168)
    allow_registration: bool = True
    max_upload_mb: int = Field(100, ge=1, le=2048)

    llm_provider: Literal["ollama", "openai", "extrativo"] = "ollama"
    llm_model: str = "llama3.1"
    llm_temperature: float = Field(0.1, ge=0.0, le=1.0)
    llm_timeout: float = 120.0
    ollama_url: str = "http://localhost:11434"
    openai_base_url: str | None = None
    openai_api_key: str | None = Field(None, validation_alias=AliasChoices("NEXO_OPENAI_API_KEY", "OPENAI_API_KEY"))
    cohere_api_key: str | None = Field(None, validation_alias=AliasChoices("NEXO_COHERE_API_KEY", "COHERE_API_KEY"))

    embed_provider: Literal["huggingface", "openai", "ollama", "hash"] = "huggingface"
    embed_model: str = "intfloat/multilingual-e5-small"
    embed_query_prefix: str = "query: "
    embed_text_prefix: str = "passage: "

    vector_store: Literal["chroma", "qdrant"] = "chroma"
    collection: str = "nexo_trechos"
    chroma_host: str | None = None
    chroma_port: int = 8001
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None

    reranker: Literal["huggingface", "cohere", "none"] = "huggingface"
    rerank_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    cohere_model: str = "rerank-v3.5"

    chunk_size: int = Field(512, ge=128, le=4096)
    chunk_overlap: int = Field(64, ge=0, le=1024)
    top_k: int = Field(12, ge=1, le=100)
    top_n: int = Field(4, ge=1, le=20)
    min_similarity: float = Field(0.15, ge=-1.0, le=1.0)
    min_rerank_score: float = Field(0.1, ge=0.0, le=1.0)
    history_turns: int = Field(3, ge=0, le=10)
    verify_answers: bool = False

    @field_validator("database_url", "secret", "openai_base_url", "openai_api_key", "cohere_api_key", "chroma_host",
                     "qdrant_url", "qdrant_api_key", mode="before")
    @classmethod
    def _blank_is_none(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def users_file(self) -> Path:
        return self.data_dir / "usuarios.json"

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'nexo.db').as_posix()}"

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def qdrant_path(self) -> Path:
        return self.data_dir / "qdrant"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.uploads_dir.mkdir(parents=True, exist_ok=True)
    return s
