from app.core.exceptions import AppError
from app.integrations.model_runtime import get_model_runtime, provider_app_error
from plugins.model_providers import ProviderError


class OllamaClient:
    """向后兼容外观；实际 Provider 由管理员运行时配置决定。"""

    def __init__(self):
        self.runtime = get_model_runtime()
        self.settings = None  # 兼容迁移期测试注入 ollama_keep_alive。

    @property
    def keep_alive(self) -> int | str:
        value = (self.settings.ollama_keep_alive if self.settings else self.runtime.config().keep_alive).strip()
        return int(value) if value.lstrip("-").isdigit() else value

    async def chat(self, system: str, user: str, json_mode: bool | dict = False) -> str:
        try:
            return await self.runtime.llm().chat(system, user, json_mode)
        except ProviderError as exc:
            raise provider_app_error(exc) from exc

    async def chat_messages(self, messages: list[dict], json_mode: bool | dict = False) -> str:
        try:
            return await self.runtime.llm().chat_messages(messages, json_mode)
        except ProviderError as exc:
            raise provider_app_error(exc) from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            vectors = await self.runtime.embedding().embed(texts)
            expected = self.runtime.config().embedding_dimension
            if any(len(vector) != expected for vector in vectors):
                raise AppError("EMBEDDING_DIMENSION_MISMATCH", f"Embedding 实际维度与配置的 {expected} 不一致", 422)
            return vectors
        except ProviderError as exc:
            raise provider_app_error(exc, "EMBEDDING_UNAVAILABLE") from exc

    async def preload(self) -> dict:
        config = self.runtime.config()
        try:
            llm = await self.runtime.llm(config).preload()
            embedding = await self.runtime.embedding(config).preload()
            actual = embedding.get("dimension")
            if actual and actual != config.embedding_dimension:
                raise AppError("EMBEDDING_DIMENSION_MISMATCH", f"Embedding 实际维度 {actual}，配置维度 {config.embedding_dimension}", 422)
            return {"llm": llm, "embedding": embedding, "keep_alive": self.keep_alive}
        except ProviderError as exc:
            raise provider_app_error(exc) from exc

    async def health(self) -> dict:
        try:
            return {"ok": True, "llm": await self.runtime.llm().health(),
                    "embedding": await self.runtime.embedding().health()}
        except ProviderError as exc:
            raise provider_app_error(exc) from exc
