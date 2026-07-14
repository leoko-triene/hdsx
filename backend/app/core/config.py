from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(Path(__file__).parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI教育智能体"
    app_env: str = "development"
    app_debug: bool = False
    serve_frontend: bool = False
    api_prefix: str = "/api/v1"
    secret_key: str = "development-only-change-me"
    access_token_minutes: int = 60

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "ai_education"
    mysql_user: str = "ai_education_app"
    mysql_password: str = "change_me"
    mysql_pool_size: int = 10
    mysql_max_overflow: int = 20

    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530
    milvus_collection: str = "edu_chunks_dev"

    # 旧 Ollama 配置，保留兼容；新部署请使用 llm_/embedding_ 配置项
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5:latest"
    ollama_embedding_model: str = "embeddinggemma:latest"

    # LLM provider：ollama / openai_compatible
    llm_provider: str = "ollama"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    # Embedding provider：ollama / openai_compatible
    embedding_provider: str = "ollama"
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int = 768

    reranker_model_path: str = Field(default="")
    reranker_device: str = "cpu"

    storage_root: Path = Path("storage")
    max_upload_mb: int = 50
    rag_chunk_size: int = 650
    rag_chunk_overlap: int = 100
    rag_vector_top_k: int = 20
    rag_keyword_top_k: int = 20
    rag_rerank_top_k: int = 8

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus

        password = quote_plus(self.mysql_password)
        return (
            f"mysql+pymysql://{self.mysql_user}:{password}@{self.mysql_host}:"
            f"{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
