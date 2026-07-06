import pytest

from services.llm_service import _make_llm_service, LLMService
from services.groq_llm_service import GroqLLMService
from services.openai_compat_llm_service import OpenAICompatLLMService
from services.failover_llm_service import FailoverLLMService


def test_factory_returns_groq_service(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "llm_provider", "groq")
    monkeypatch.setattr(config.settings, "groq_api_key", "test-key")
    service = _make_llm_service()
    assert isinstance(service, GroqLLMService)


def test_factory_returns_openai_compat_for_mlx(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "llm_provider", "mlx")
    monkeypatch.setattr(config.settings, "llm_base_url", "http://localhost:8080/v1")
    monkeypatch.setattr(config.settings, "llm_model_name", "test-model")
    service = _make_llm_service()
    assert isinstance(service, OpenAICompatLLMService)


def test_factory_falls_back_to_ollama(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "llm_provider", "ollama")
    service = _make_llm_service()
    assert isinstance(service, LLMService)


def test_factory_unknown_provider_falls_back_to_ollama(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "llm_provider", "unknown_provider")
    service = _make_llm_service()
    assert isinstance(service, LLMService)


def test_factory_returns_openai_compat_for_gemini_single_key(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "gemini_api_key", "key-1")
    monkeypatch.setattr(config.settings, "gemini_api_key_2", "")
    service = _make_llm_service()
    assert isinstance(service, OpenAICompatLLMService)


def test_factory_returns_failover_for_gemini_two_keys(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "gemini_api_key", "key-1")
    monkeypatch.setattr(config.settings, "gemini_api_key_2", "key-2")
    service = _make_llm_service()
    assert isinstance(service, FailoverLLMService)
    assert len(service._services) == 2


def test_factory_gemini_no_keys_raises(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "gemini_api_key", "")
    monkeypatch.setattr(config.settings, "gemini_api_key_2", "")
    with pytest.raises(ValueError):
        _make_llm_service()
