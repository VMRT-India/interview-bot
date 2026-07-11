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


def _clear_extra_failover_keys(monkeypatch):
    # Isolates tests from real NVIDIA/Groq/Cerebras keys that may be set in a local
    # .env — without this, tests would silently pick up production credentials.
    import config
    monkeypatch.setattr(config.settings, "nvidia_api_key", "")
    monkeypatch.setattr(config.settings, "groq_api_key", "")
    monkeypatch.setattr(config.settings, "cerebras_api_key", "")


def test_factory_returns_openai_compat_for_gemini_single_key(monkeypatch):
    import config
    _clear_extra_failover_keys(monkeypatch)
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "gemini_api_key", "key-1")
    monkeypatch.setattr(config.settings, "gemini_api_key_2", "")
    service = _make_llm_service()
    assert isinstance(service, OpenAICompatLLMService)


def test_factory_returns_failover_for_gemini_two_keys(monkeypatch):
    import config
    _clear_extra_failover_keys(monkeypatch)
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "gemini_api_key", "key-1")
    monkeypatch.setattr(config.settings, "gemini_api_key_2", "key-2")
    service = _make_llm_service()
    assert isinstance(service, FailoverLLMService)
    assert len(service._services) == 2


def test_factory_appends_groq_fallback_to_gemini_when_groq_key_set(monkeypatch):
    # Phase 12 — a Groq key already configured for BYOK gets reused as a fallback
    # tier, since it's a completely separate quota pool from Gemini's. Groq is tried
    # before Gemini in the priority order (see chain ordering test below).
    import config
    _clear_extra_failover_keys(monkeypatch)
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "gemini_api_key", "key-1")
    monkeypatch.setattr(config.settings, "gemini_api_key_2", "")
    monkeypatch.setattr(config.settings, "groq_api_key", "groq-key")
    service = _make_llm_service()
    assert isinstance(service, FailoverLLMService)
    assert len(service._services) == 2
    assert isinstance(service._services[0], GroqLLMService)


def test_factory_gemini_no_keys_raises(monkeypatch):
    import config
    _clear_extra_failover_keys(monkeypatch)
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "gemini_api_key", "")
    monkeypatch.setattr(config.settings, "gemini_api_key_2", "")
    with pytest.raises(ValueError):
        _make_llm_service()


def test_factory_full_chain_order_nvidia_groq_gemini_cerebras(monkeypatch):
    # Phase 12 — priority order: NVIDIA first, then Groq, then both Gemini keys,
    # then Cerebras last (its free tier's 8K context cap makes it a last resort).
    import config
    monkeypatch.setattr(config.settings, "llm_provider", "gemini")
    monkeypatch.setattr(config.settings, "nvidia_api_key", "nvidia-key")
    monkeypatch.setattr(config.settings, "groq_api_key", "groq-key")
    monkeypatch.setattr(config.settings, "gemini_api_key", "gem-key-1")
    monkeypatch.setattr(config.settings, "gemini_api_key_2", "gem-key-2")
    monkeypatch.setattr(config.settings, "cerebras_api_key", "cerebras-key")
    service = _make_llm_service()
    assert isinstance(service, FailoverLLMService)
    assert len(service._services) == 5
    assert isinstance(service._services[0], OpenAICompatLLMService)
    assert service._services[0]._client.base_url == "https://integrate.api.nvidia.com/v1/"
    assert isinstance(service._services[1], GroqLLMService)
    assert isinstance(service._services[2], OpenAICompatLLMService)
    assert isinstance(service._services[3], OpenAICompatLLMService)
    assert isinstance(service._services[4], OpenAICompatLLMService)
    assert service._services[4]._client.base_url == "https://api.cerebras.ai/v1/"
