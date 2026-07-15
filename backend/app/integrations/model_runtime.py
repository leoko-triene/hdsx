from __future__ import annotations

import re
import sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.exceptions import AppError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from plugins.model_providers import (  # noqa: E402
    EncryptedModelConfigStore, ModelRuntimeConfig, ProviderError,
    build_embedding_provider, build_llm_provider,
)


class ModelRuntimeManager:
    """主工程薄适配：提供默认值、校验、加密持久化和异常协议转换。"""

    def __init__(self):
        settings = get_settings()
        storage_root = settings.storage_root if settings.storage_root.is_absolute() else PROJECT_ROOT / settings.storage_root
        config_path = storage_root / "system" / "model-providers.enc"
        self.store = EncryptedModelConfigStore(config_path, settings.secret_key)

    @staticmethod
    def defaults() -> ModelRuntimeConfig:
        settings = get_settings()
        return ModelRuntimeConfig(
            llm_base_url=settings.ollama_base_url,
            llm_model=settings.ollama_llm_model,
            llm_temperature=settings.llm_temperature,
            embedding_base_url=settings.ollama_base_url,
            embedding_model=settings.ollama_embedding_model,
            embedding_dimension=768,
            vector_collection=settings.milvus_collection,
            keep_alive=settings.ollama_keep_alive,
        )

    def config(self) -> ModelRuntimeConfig:
        try:
            return self.store.load(self.defaults())
        except RuntimeError as exc:
            raise AppError("MODEL_CONFIG_INVALID", str(exc), 500) from exc

    @staticmethod
    def validate(config: ModelRuntimeConfig) -> None:
        if config.llm_provider not in {"ollama", "openai_compatible"}:
            raise AppError("MODEL_CONFIG_INVALID", "不支持的 LLM Provider", 422)
        if config.embedding_provider not in {"ollama", "openai_compatible"}:
            raise AppError("MODEL_CONFIG_INVALID", "不支持的 Embedding Provider", 422)
        for label, value in (("LLM 地址", config.llm_base_url), ("Embedding 地址", config.embedding_base_url)):
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise AppError("MODEL_CONFIG_INVALID", f"{label}必须是 http/https 地址", 422)
        if not config.llm_model.strip() or not config.embedding_model.strip():
            raise AppError("MODEL_CONFIG_INVALID", "模型名称不能为空", 422)
        if not 1 <= config.embedding_dimension <= 65536:
            raise AppError("MODEL_CONFIG_INVALID", "Embedding 维度必须在 1～65536 之间", 422)
        if not re.fullmatch(r"[A-Za-z0-9_]{1,255}", config.vector_collection):
            raise AppError("MODEL_CONFIG_INVALID", "Milvus collection 只能包含字母、数字和下划线", 422)
        if config.llm_temperature is not None and not 0.0 <= config.llm_temperature <= 2.0:
            raise AppError("MODEL_CONFIG_INVALID", "LLM temperature 必须在 0.0～2.0 之间", 422)

    def merged(self, values: dict, *, preserve_keys: bool = True) -> ModelRuntimeConfig:
        current = self.config()
        data = {**asdict(current), **{key: value for key, value in values.items() if value is not None}}
        if preserve_keys:
            if not values.get("llm_api_key"):
                data["llm_api_key"] = current.llm_api_key
            if not values.get("embedding_api_key"):
                data["embedding_api_key"] = current.embedding_api_key
        config = ModelRuntimeConfig(**data)
        self.validate(config)
        return config

    def save(self, config: ModelRuntimeConfig) -> None:
        self.validate(config)
        try:
            self.store.save(config)
        except RuntimeError as exc:
            raise AppError("MODEL_CONFIG_SAVE_FAILED", str(exc), 500) from exc

    def llm(self, config: ModelRuntimeConfig | None = None):
        try:
            return build_llm_provider(config or self.config())
        except ProviderError as exc:
            raise AppError("MODEL_CONFIG_INVALID", str(exc), 422) from exc

    def embedding(self, config: ModelRuntimeConfig | None = None):
        try:
            return build_embedding_provider(config or self.config())
        except ProviderError as exc:
            raise AppError("MODEL_CONFIG_INVALID", str(exc), 422) from exc


@lru_cache
def get_model_runtime() -> ModelRuntimeManager:
    return ModelRuntimeManager()


def provider_app_error(exc: Exception, code: str = "MODEL_UNAVAILABLE") -> AppError:
    return AppError(code, str(exc), 503)
