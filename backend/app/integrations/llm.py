"""LLM / Embedding Provider 抽象层与工厂。

新增 provider 时：
1. 在 backend/app/integrations/ 下实现 LLMProvider / EmbeddingProvider 子类。
2. 在 _LLM_PROVIDERS / _EMBEDDING_PROVIDERS 字典中注册。
3. 业务代码统一使用 get_llm_provider() / get_embedding_provider()。
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from app.core.config import get_settings
from app.core.exceptions import AppError


class LLMProvider(ABC):
    """大语言模型调用抽象。"""

    name: ClassVar[str] = ""

    @abstractmethod
    async def chat(self, system: str, user: str, json_mode: bool | dict = False) -> str:
        """调用 LLM 返回文本。json_mode 为 True 时要求返回合法 JSON；为 dict 时作为 schema 参考。"""

    @abstractmethod
    async def health(self) -> dict:
        """返回 {"ok": bool, ...} 形式的健康状态。"""

    def _raise_unavailable(self, exc: Exception) -> None:
        raise AppError("MODEL_UNAVAILABLE", f"{self.name or 'LLM'} 调用失败：{exc}", 503) from exc


class EmbeddingProvider(ABC):
    """文本嵌入模型调用抽象。"""

    name: ClassVar[str] = ""

    @abstractmethod
    async def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """对 texts 分批编码，返回与输入等长的向量列表。"""

    @abstractmethod
    async def health(self) -> dict:
        """返回 {"ok": bool, ...} 形式的健康状态。"""

    def _raise_unavailable(self, exc: Exception) -> None:
        raise AppError("EMBEDDING_UNAVAILABLE", f"{self.name or 'Embedding'} 调用失败：{exc}", 503) from exc


_LLM_PROVIDERS: dict[str, type[LLMProvider]] = {}
_EMBEDDING_PROVIDERS: dict[str, type[EmbeddingProvider]] = {}


def register_llm_provider(name: str, cls: type[LLMProvider]) -> None:
    _LLM_PROVIDERS[name] = cls


def register_embedding_provider(name: str, cls: type[EmbeddingProvider]) -> None:
    _EMBEDDING_PROVIDERS[name] = cls


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider
    cls = _LLM_PROVIDERS.get(provider)
    if not cls:
        raise AppError("UNKNOWN_LLM_PROVIDER", f"不支持的 LLM provider: {provider}", 500)
    return cls()


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.embedding_provider
    cls = _EMBEDDING_PROVIDERS.get(provider)
    if not cls:
        raise AppError("UNKNOWN_EMBEDDING_PROVIDER", f"不支持的 Embedding provider: {provider}", 500)
    return cls()


# 延迟导入具体实现，避免循环依赖
from app.integrations.ollama import OllamaEmbeddingProvider, OllamaLLMProvider  # noqa: E402
from app.integrations.openai_compatible import (  # noqa: E402
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleLLMProvider,
)

register_llm_provider("ollama", OllamaLLMProvider)
register_llm_provider("openai_compatible", OpenAICompatibleLLMProvider)
register_embedding_provider("ollama", OllamaEmbeddingProvider)
register_embedding_provider("openai_compatible", OpenAICompatibleEmbeddingProvider)
