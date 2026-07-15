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
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5:latest"
    ollama_embedding_model: str = "embeddinggemma:latest"
    llm_temperature: float | None = None
    model_warmup_enabled: bool = True
    model_warmup_strict: bool = True
    ollama_keep_alive: str = "-1"
    model_warmup_timeout_seconds: int = 300
    reranker_model_path: str = Field(default="")
    reranker_device: str = "cpu"
    mcp_remote_enabled: bool = False
    mcp_allowed_hosts: str = ""
    web_fetch_timeout_seconds: int = 20
    web_fetch_max_bytes: int = 2_000_000
    web_fetch_max_chars: int = 50_000
    web_import_expire_hours: int = 24
    web_fetch_user_agent: str = "EduAgentKnowledgeBot/1.0 (+course knowledge import)"

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
