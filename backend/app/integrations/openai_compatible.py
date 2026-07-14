"""OpenAI 兼容 API Provider。

支持 OpenAI、DeepSeek、阿里云百炼（DashScope）、智谱 AI 等所有兼容 /v1/chat/completions
和 /v1/embeddings 的服务。
"""

import json

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.integrations.llm import EmbeddingProvider, LLMProvider


class OpenAICompatibleLLMProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self):
        self.settings = get_settings()

    @property
    def _base_url(self) -> str:
        return (self.settings.llm_base_url or "").rstrip("/")

    @property
    def _api_key(self) -> str | None:
        return self.settings.llm_api_key

    @property
    def _model(self) -> str:
        if self.settings.llm_model:
            return self.settings.llm_model
        raise AppError("LLM_MODEL_MISSING", "未配置 LLM_MODEL", 500)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def chat(self, system: str, user: str, json_mode: bool | dict = False) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
        }
        if json_mode:
            # OpenAI 兼容接口的 JSON mode：设置 response_format 并在 prompt 中强调只返回 JSON
            payload["response_format"] = {"type": "json_object"}
            if isinstance(json_mode, dict):
                schema_hint = (
                    "\n\n请严格按以下 JSON Schema 返回，不要包含代码块或额外说明：\n"
                    + json.dumps(json_mode, ensure_ascii=False)
                )
                payload["messages"][1]["content"] = user + schema_hint
            else:
                payload["messages"][1]["content"] = user + "\n\n请只返回合法 JSON，不要包含代码块或额外说明。"
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return content
        except (httpx.HTTPError, KeyError) as exc:
            self._raise_unavailable(exc)

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                # 先尝试 /models，部分服务可能不支持，失败则回退到简单 GET
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"} if self._api_key else {},
                )
                response.raise_for_status()
                models = [m.get("id") for m in response.json().get("data", [])]
                return {"ok": True, "provider": "openai_compatible", "models": models}
        except (httpx.HTTPError, KeyError):
            # fallback：尝试 POST 一个极小的 chat completion
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=self._headers(),
                        json={"model": self._model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                    )
                    response.raise_for_status()
                    return {"ok": True, "provider": "openai_compatible"}
            except (httpx.HTTPError, KeyError) as exc:
                return {"ok": False, "provider": "openai_compatible", "error": str(exc)}


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    name = "openai_compatible"

    def __init__(self):
        self.settings = get_settings()

    @property
    def _base_url(self) -> str:
        return (self.settings.embedding_base_url or "").rstrip("/")

    @property
    def _api_key(self) -> str | None:
        return self.settings.embedding_api_key

    @property
    def _model(self) -> str:
        if self.settings.embedding_model:
            return self.settings.embedding_model
        raise AppError("EMBEDDING_MODEL_MISSING", "未配置 EMBEDDING_MODEL", 500)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def embed(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        try:
            all_embeddings: list[list[float]] = []
            async with httpx.AsyncClient(timeout=120) as client:
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    response = await client.post(
                        f"{self._base_url}/embeddings",
                        headers=self._headers(),
                        json={"model": self._model, "input": batch},
                    )
                    response.raise_for_status()
                    data = response.json()
                    embeddings = [item["embedding"] for item in data["data"]]
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
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self._base_url}/embeddings",
                    headers=self._headers(),
                    json={"model": self._model, "input": ["test"]},
                )
                response.raise_for_status()
                return {"ok": True, "provider": "openai_compatible"}
        except (httpx.HTTPError, KeyError) as exc:
            return {"ok": False, "provider": "openai_compatible", "error": str(exc)}
