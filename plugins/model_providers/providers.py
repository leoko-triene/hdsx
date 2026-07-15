from __future__ import annotations

import json
import httpx

from .contracts import EmbeddingProvider, LLMProvider, ModelRuntimeConfig, ProviderError


def _base(value: str) -> str:
    return value.rstrip("/")


def _bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"} if key else {}


class OllamaLLMProvider(LLMProvider):
    def __init__(self, config: ModelRuntimeConfig):
        self.config = config

    @property
    def keep_alive(self) -> int | str:
        value = self.config.keep_alive.strip()
        return int(value) if value.lstrip("-").isdigit() else value

    async def chat(self, system: str, user: str, json_mode: bool | dict = False) -> str:
        if isinstance(json_mode, dict):
            system = (
                f"{system}\n\n你必须只输出满足以下 JSON Schema 的 JSON 对象，不要输出 Markdown 代码块或额外说明：\n"
                f"{json.dumps(json_mode, ensure_ascii=False)}"
            )
        payload: dict = {
            "model": self.config.llm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False, "keep_alive": self.keep_alive, "options": {"temperature": 0.2},
        }
        if json_mode:
            payload["format"] = json_mode if isinstance(json_mode, dict) else "json"
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(f"{_base(self.config.llm_base_url)}/api/chat", json=payload)
                response.raise_for_status()
                content = response.json()["message"]["content"]
                if not isinstance(content, str):
                    raise KeyError("message.content")
                return content
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            raise ProviderError(f"Ollama LLM 调用失败：{exc}") from exc

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{_base(self.config.llm_base_url)}/api/tags")
                response.raise_for_status()
                names = [item.get("name", "") for item in response.json().get("models", [])]
            return {"ok": True, "provider": "ollama", "model": self.config.llm_model, "models": names}
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            raise ProviderError(f"Ollama 服务检查失败：{exc}") from exc

    async def preload(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(
                    f"{_base(self.config.llm_base_url)}/api/generate",
                    json={"model": self.config.llm_model, "prompt": "模型预热", "stream": False,
                          "keep_alive": self.keep_alive, "options": {"num_predict": 1}},
                )
                response.raise_for_status()
            return {"ok": True, "provider": "ollama", "model": self.config.llm_model,
                    "keep_alive": self.keep_alive}
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama LLM 预热失败：{exc}") from exc


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: ModelRuntimeConfig):
        self.config = config

    async def embed(self, texts: list[str]) -> list[list[float]]:
        value = self.config.keep_alive.strip()
        keep_alive: int | str = int(value) if value.lstrip("-").isdigit() else value
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{_base(self.config.embedding_base_url)}/api/embed",
                    json={"model": self.config.embedding_model, "input": texts, "keep_alive": keep_alive},
                )
                response.raise_for_status()
                vectors = response.json()["embeddings"]
            if len(vectors) != len(texts):
                raise ProviderError("Embedding 返回数量与输入数量不一致")
            return vectors
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            raise ProviderError(f"Ollama Embedding 调用失败：{exc}") from exc

    async def health(self) -> dict:
        vectors = await self.embed(["连接测试"])
        return {"ok": True, "provider": "ollama", "model": self.config.embedding_model,
                "dimension": len(vectors[0])}

    async def preload(self) -> dict:
        return await self.health()


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(self, config: ModelRuntimeConfig):
        self.config = config

    async def chat(self, system: str, user: str, json_mode: bool | dict = False) -> str:
        if isinstance(json_mode, dict):
            system = (
                f"{system}\n\n你必须只输出满足以下 JSON Schema 的 JSON 对象，不要输出 Markdown 代码块或额外说明：\n"
                f"{json.dumps(json_mode, ensure_ascii=False)}"
            )
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        payload: dict = {
            "model": self.config.llm_model,
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{_base(self.config.llm_base_url)}/chat/completions", json=payload,
                    headers=_bearer(self.config.llm_api_key),
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise KeyError("choices[0].message.content")
                return content
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"OpenAI 兼容 LLM 调用失败：{exc}") from exc

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    f"{_base(self.config.llm_base_url)}/models",
                    headers=_bearer(self.config.llm_api_key),
                )
                response.raise_for_status()
            return {"ok": True, "provider": "openai_compatible", "model": self.config.llm_model}
        except httpx.HTTPError as exc:
            raise ProviderError(f"OpenAI 兼容 LLM 服务检查失败：{exc}") from exc


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    def __init__(self, config: ModelRuntimeConfig):
        self.config = config

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{_base(self.config.embedding_base_url)}/embeddings",
                    json={"model": self.config.embedding_model, "input": texts},
                    headers=_bearer(self.config.embedding_api_key),
                )
                response.raise_for_status()
                rows = sorted(response.json()["data"], key=lambda item: item.get("index", 0))
                vectors = [item["embedding"] for item in rows]
            if len(vectors) != len(texts):
                raise ProviderError("Embedding 返回数量与输入数量不一致")
            return vectors
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            raise ProviderError(f"OpenAI 兼容 Embedding 调用失败：{exc}") from exc

    async def health(self) -> dict:
        vectors = await self.embed(["连接测试"])
        return {"ok": True, "provider": "openai_compatible", "model": self.config.embedding_model,
                "dimension": len(vectors[0])}


def build_llm_provider(config: ModelRuntimeConfig) -> LLMProvider:
    if config.llm_provider == "ollama":
        return OllamaLLMProvider(config)
    if config.llm_provider == "openai_compatible":
        return OpenAICompatibleLLMProvider(config)
    raise ProviderError(f"不支持的 LLM Provider：{config.llm_provider}")


def build_embedding_provider(config: ModelRuntimeConfig) -> EmbeddingProvider:
    if config.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(config)
    if config.embedding_provider == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider(config)
    raise ProviderError(f"不支持的 Embedding Provider：{config.embedding_provider}")
