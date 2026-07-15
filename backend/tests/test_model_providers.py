import asyncio
from pathlib import Path

import httpx

from app.integrations.model_runtime import ModelRuntimeConfig, ModelRuntimeManager
from plugins.model_providers import EncryptedModelConfigStore
from plugins.model_providers.providers import OllamaEmbeddingProvider, OllamaLLMProvider, OpenAICompatibleLLMProvider


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


def test_openai_compatible_llm_uses_json_response_format(monkeypatch):
    captured = {}

    async def post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": '{"ok":true}'}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    config = ModelRuntimeConfig(llm_provider="openai_compatible", llm_base_url="https://example.test/v1", llm_model="test-model", llm_api_key="secret")
    content = asyncio.run(OpenAICompatibleLLMProvider(config).chat("system", "user", True))
    assert content == '{"ok":true}'
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["headers"]["Authorization"] == "Bearer secret"
    # 默认不发送 temperature，兼容 Kimi 等仅接受 temperature=1.0 的服务
    assert "temperature" not in captured["json"]


def test_openai_compatible_llm_appends_json_schema(monkeypatch):
    captured = {}

    async def post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": '{"score":1}'}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    config = ModelRuntimeConfig(llm_provider="openai_compatible", llm_base_url="https://example.test/v1", llm_model="test-model")
    asyncio.run(OpenAICompatibleLLMProvider(config).chat("评分", "回答", {"type": "object", "required": ["score"]}))
    assert "JSON Schema" in captured["json"]["messages"][0]["content"]
    assert '"score"' in captured["json"]["messages"][0]["content"]


def test_openai_compatible_llm_sends_temperature_when_configured(monkeypatch):
    captured = {}

    async def post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    config = ModelRuntimeConfig(
        llm_provider="openai_compatible",
        llm_base_url="https://example.test/v1",
        llm_model="test-model",
        llm_temperature=0.7,
    )
    asyncio.run(OpenAICompatibleLLMProvider(config).chat("system", "user"))
    assert captured["json"]["temperature"] == 0.7


def test_ollama_llm_uses_default_temperature_when_not_configured(monkeypatch):
    captured = {}

    async def post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"message": {"content": "ok"}})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    asyncio.run(OllamaLLMProvider(ModelRuntimeConfig()).chat("system", "user"))
    assert captured["json"]["options"]["temperature"] == 0.2


def test_ollama_llm_uses_configured_temperature(monkeypatch):
    captured = {}

    async def post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse({"message": {"content": "ok"}})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    asyncio.run(OllamaLLMProvider(ModelRuntimeConfig(llm_temperature=0.8)).chat("system", "user"))
    assert captured["json"]["options"]["temperature"] == 0.8


def test_ollama_embedding_returns_all_vectors(monkeypatch):
    async def post(*args, **kwargs):
        return FakeResponse({"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    vectors = asyncio.run(OllamaEmbeddingProvider(ModelRuntimeConfig()).embed(["a", "b"]))
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


def test_encrypted_store_does_not_write_plaintext(tmp_path: Path):
    target = tmp_path / "model-settings.enc"
    store = EncryptedModelConfigStore(target, "unit-test-secret")
    config = ModelRuntimeConfig(llm_api_key="sk-not-plaintext", llm_model="custom-model")
    store.save(config)
    assert b"sk-not-plaintext" not in target.read_bytes()
    restored = store.load(ModelRuntimeConfig())
    assert restored.llm_api_key == "sk-not-plaintext"
    assert restored.llm_model == "custom-model"


def test_public_config_never_returns_api_keys():
    public = ModelRuntimeConfig(llm_api_key="llm-secret", embedding_api_key="embedding-secret").public_dict()
    assert "llm_api_key" not in public
    assert "embedding_api_key" not in public
    assert public["llm_api_key_configured"] is True
    assert public["embedding_api_key_configured"] is True


def test_model_runtime_rejects_invalid_temperature():
    config = ModelRuntimeConfig(llm_temperature=-0.1)
    try:
        ModelRuntimeManager.validate(config)
    except Exception as exc:  # noqa: BLE001
        assert "temperature" in str(exc)
    else:
        raise AssertionError("expected validation error for negative temperature")


def test_model_runtime_accepts_none_temperature():
    # 不应抛出异常
    ModelRuntimeManager.validate(ModelRuntimeConfig(llm_temperature=None))
