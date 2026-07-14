"""Ollama Provider 实现。

保留旧 OllamaClient 作为兼容包装；新业务请使用 OllamaLLMProvider / OllamaEmbeddingProvider。
"""

import warnings

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.integrations.llm import EmbeddingProvider, LLMProvider


class OllamaLLMProvider(LLMProvider):
    name = "ollama"

    def __init__(self):
        self.settings = get_settings()

    @property
    def _base_url(self) -> str:
        return self.settings.llm_base_url or self.settings.ollama_base_url

    @property
    def _model(self) -> str:
        return self.settings.llm_model or self.settings.ollama_llm_model

    async def chat(self, system: str, user: str, json_mode: bool | dict = False) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if json_mode:
            payload["format"] = json_mode if isinstance(json_mode, dict) else "json"
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
                return response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError) as exc:
            self._raise_unavailable(exc)

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{self._base_url}/api/tags")
            response.raise_for_status()
            names = [item["name"] for item in response.json().get("models", [])]
            return {"ok": True, "provider": "ollama", "models": names}


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self):
        self.settings = get_settings()

    @property
    def _base_url(self) -> str:
        return self.settings.embedding_base_url or self.settings.ollama_base_url

    @property
    def _model(self) -> str:
        return self.settings.embedding_model or self.settings.ollama_embedding_model

    async def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        try:
            all_embeddings: list[list[float]] = []
            async with httpx.AsyncClient(timeout=120) as client:
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    response = await client.post(
                        f"{self._base_url}/api/embed",
                        json={"model": self._model, "input": batch},
                    )
                    response.raise_for_status()
                    embeddings = response.json()["embeddings"]
                    if len(embeddings) != len(batch):
                        raise AppError(
                            "EMBEDDING_MISMATCH",
                            f"Embedding 返回数量不匹配：请求 {len(batch)} 条，返回 {len(embeddings)} 条",
                            503,
                        )
                    all_embeddings.extend(embeddings)
            return all_embeddings
        except (httpx.HTTPError, KeyError) as exc:
            self._raise_unavailable(exc)

    async def health(self) -> dict:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{self._base_url}/api/tags")
            response.raise_for_status()
            return {"ok": True, "provider": "ollama"}


class OllamaClient:
    """旧版兼容客户端，功能等同于 OllamaLLMProvider + OllamaEmbeddingProvider。"""

    def __init__(self):
        warnings.warn(
            "OllamaClient 已弃用，请使用 get_llm_provider() / get_embedding_provider() 或 OllamaLLMProvider / OllamaEmbeddingProvider",
            DeprecationWarning,
            stacklevel=2,
        )
        self._llm = OllamaLLMProvider()
        self._embed = OllamaEmbeddingProvider()

    async def chat(self, system: str, user: str, json_mode: bool | dict = False) -> str:
        return await self._llm.chat(system, user, json_mode)

    async def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return await self._embed.embed(texts, batch_size)

    async def health(self) -> dict:
        return await self._llm.health()
