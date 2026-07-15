from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any


class ProviderError(RuntimeError):
    """模型服务不可用或返回内容不符合协议。"""


@dataclass(slots=True)
class ModelRuntimeConfig:
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:latest"
    llm_api_key: str = ""
    llm_temperature: float | None = None
    embedding_provider: str = "ollama"
    embedding_base_url: str = "http://localhost:11434"
    embedding_model: str = "embeddinggemma:latest"
    embedding_api_key: str = ""
    embedding_dimension: int = 768
    vector_collection: str = "edu_chunks_dev"
    keep_alive: str = "-1"

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("llm_api_key", None)
        value.pop("embedding_api_key", None)
        value["llm_api_key_configured"] = bool(self.llm_api_key)
        value["embedding_api_key_configured"] = bool(self.embedding_api_key)
        return value


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, system: str, user: str, json_mode: bool | dict = False) -> str: ...

    async def chat_messages(self, messages: list[dict], json_mode: bool | dict = False) -> str:
        system = ""
        user = ""
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            elif m["role"] == "user":
                user = m["content"]
        return await self.chat(system, user, json_mode)

    @abstractmethod
    async def health(self) -> dict: ...

    async def preload(self) -> dict:
        return await self.health()


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def health(self) -> dict: ...

    async def preload(self) -> dict:
        return await self.health()
