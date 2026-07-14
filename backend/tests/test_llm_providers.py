import sys
from types import SimpleNamespace
from unittest import mock

import httpx
import pytest

from app.core.exceptions import AppError
from app.integrations.llm import (
    get_embedding_provider,
    get_llm_provider,
    register_embedding_provider,
    register_llm_provider,
)
from app.integrations.ollama import OllamaEmbeddingProvider, OllamaLLMProvider
from app.integrations.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleLLMProvider,
)


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


def _fake_response(json_data, status_code=200):
    return _FakeResponse(json_data, status_code)


def _patch_post(monkeypatch, json_data, status_code=200):
    async def _mock_post(*args, **kwargs):
        return _fake_response(json_data, status_code)

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)


def _patch_get(monkeypatch, json_data, status_code=200):
    async def _mock_get(*args, **kwargs):
        return _fake_response(json_data, status_code)

    monkeypatch.setattr(httpx.AsyncClient, "get", _mock_get)


class TestOllamaLLMProvider:
    @pytest.fixture
    def provider(self, monkeypatch):
        p = OllamaLLMProvider()
        monkeypatch.setattr(p, "settings", SimpleNamespace(
            llm_base_url="http://localhost:11434",
            llm_model="qwen2.5:latest",
            ollama_base_url="http://localhost:11434",
            ollama_llm_model="qwen2.5:latest",
        ))
        return p

    @pytest.mark.asyncio
    async def test_chat_success(self, provider, monkeypatch):
        _patch_post(monkeypatch, {"message": {"content": "hello"}})
        result = await provider.chat("system", "user")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_chat_json_mode(self, provider, monkeypatch):
        _patch_post(monkeypatch, {"message": {"content": '{"score": 5}'}})
        result = await provider.chat("system", "user", json_mode=True)
        assert result == '{"score": 5}'

    @pytest.mark.asyncio
    async def test_chat_failure(self, provider, monkeypatch):
        async def _raise(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx.AsyncClient, "post", _raise)
        with pytest.raises(AppError) as exc_info:
            await provider.chat("system", "user")
        assert exc_info.value.code == "MODEL_UNAVAILABLE"


class TestOllamaEmbeddingProvider:
    @pytest.fixture
    def provider(self, monkeypatch):
        p = OllamaEmbeddingProvider()
        monkeypatch.setattr(p, "settings", SimpleNamespace(
            embedding_base_url="http://localhost:11434",
            embedding_model="embeddinggemma:latest",
            ollama_base_url="http://localhost:11434",
            ollama_embedding_model="embeddinggemma:latest",
        ))
        return p

    @pytest.mark.asyncio
    async def test_embed_success(self, provider, monkeypatch):
        _patch_post(monkeypatch, {"embeddings": [[0.1, 0.2], [0.3, 0.4]]})
        result = await provider.embed(["a", "b"])
        assert len(result) == 2
        assert result[0] == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_embed_mismatch(self, provider, monkeypatch):
        _patch_post(monkeypatch, {"embeddings": [[0.1, 0.2]]})
        with pytest.raises(AppError) as exc_info:
            await provider.embed(["a", "b"])
        assert exc_info.value.code == "EMBEDDING_MISMATCH"


class TestOpenAICompatibleLLMProvider:
    @pytest.fixture
    def provider(self, monkeypatch):
        p = OpenAICompatibleLLMProvider()
        monkeypatch.setattr(p, "settings", SimpleNamespace(
            llm_base_url="https://api.example.com/v1",
            llm_api_key="sk-test",
            llm_model="gpt-test",
        ))
        return p

    @pytest.mark.asyncio
    async def test_chat_success(self, provider, monkeypatch):
        _patch_post(monkeypatch, {"choices": [{"message": {"content": "hi"}}]})
        result = await provider.chat("system", "user")
        assert result == "hi"

    @pytest.mark.asyncio
    async def test_chat_json_mode(self, provider, monkeypatch):
        captured = {}

        async def _capture(*args, **kwargs):
            captured["json"] = kwargs.get("json")
            return _fake_response({"choices": [{"message": {"content": '{"a": 1}'}}]})

        monkeypatch.setattr(httpx.AsyncClient, "post", _capture)
        result = await provider.chat("system", "user", json_mode=True)
        assert result == '{"a": 1}'
        assert captured["json"]["response_format"]["type"] == "json_object"


class TestOpenAICompatibleEmbeddingProvider:
    @pytest.fixture
    def provider(self, monkeypatch):
        p = OpenAICompatibleEmbeddingProvider()
        monkeypatch.setattr(p, "settings", SimpleNamespace(
            embedding_base_url="https://api.example.com/v1",
            embedding_api_key="sk-test",
            embedding_model="text-embedding-test",
        ))
        return p

    @pytest.mark.asyncio
    async def test_embed_success(self, provider, monkeypatch):
        _patch_post(monkeypatch, {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]})
        result = await provider.embed(["a", "b"])
        assert len(result) == 2


class TestProviderFactory:
    def test_get_llm_provider_ollama(self, monkeypatch):
        # 避免污染全局设置，直接 patch 工厂内部使用的 get_settings
        from app.integrations import llm as llm_module

        def _fake_settings():
            return SimpleNamespace(llm_provider="ollama")

        monkeypatch.setattr(llm_module, "get_settings", _fake_settings)
        provider = get_llm_provider()
        assert isinstance(provider, OllamaLLMProvider)

    def test_get_llm_provider_openai(self, monkeypatch):
        from app.integrations import llm as llm_module

        def _fake_settings():
            return SimpleNamespace(llm_provider="openai_compatible")

        monkeypatch.setattr(llm_module, "get_settings", _fake_settings)
        provider = get_llm_provider()
        assert isinstance(provider, OpenAICompatibleLLMProvider)

    def test_get_embedding_provider_ollama(self, monkeypatch):
        from app.integrations import llm as llm_module

        def _fake_settings():
            return SimpleNamespace(embedding_provider="ollama")

        monkeypatch.setattr(llm_module, "get_settings", _fake_settings)
        provider = get_embedding_provider()
        assert isinstance(provider, OllamaEmbeddingProvider)

    def test_unknown_provider(self, monkeypatch):
        from app.integrations import llm as llm_module

        def _fake_settings():
            return SimpleNamespace(llm_provider="unknown")

        monkeypatch.setattr(llm_module, "get_settings", _fake_settings)
        with pytest.raises(AppError) as exc_info:
            get_llm_provider()
        assert exc_info.value.code == "UNKNOWN_LLM_PROVIDER"
