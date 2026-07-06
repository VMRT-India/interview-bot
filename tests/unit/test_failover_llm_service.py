import pytest

from services.failover_llm_service import FailoverLLMService


class _FakeService:
    def __init__(self, generate_result=None, generate_exc=None, stream_tokens=None, stream_exc=None,
                 stream_exc_after=0, health=True):
        self.generate_result = generate_result
        self.generate_exc = generate_exc
        self.stream_tokens = stream_tokens or []
        self.stream_exc = stream_exc
        self.stream_exc_after = stream_exc_after
        self.health = health
        self.generate_calls = 0
        self.stream_calls = 0

    async def generate(self, prompt, system_prompt="", json_mode=False):
        self.generate_calls += 1
        if self.generate_exc:
            raise self.generate_exc
        return self.generate_result

    async def stream_generate(self, prompt, system_prompt=""):
        self.stream_calls += 1
        for i, token in enumerate(self.stream_tokens):
            if self.stream_exc and i == self.stream_exc_after:
                raise self.stream_exc
            yield token
        if self.stream_exc and self.stream_exc_after >= len(self.stream_tokens):
            raise self.stream_exc

    async def health_check(self):
        return self.health


def test_requires_at_least_one_service():
    with pytest.raises(ValueError):
        FailoverLLMService([])


@pytest.mark.asyncio
async def test_generate_uses_first_service_on_success():
    a = _FakeService(generate_result="hello")
    b = _FakeService(generate_result="world")
    svc = FailoverLLMService([a, b])
    result = await svc.generate("prompt")
    assert result == "hello"
    assert a.generate_calls == 1
    assert b.generate_calls == 0


@pytest.mark.asyncio
async def test_generate_fails_over_to_second_service():
    a = _FakeService(generate_exc=RuntimeError("rate limited"))
    b = _FakeService(generate_result="fallback")
    svc = FailoverLLMService([a, b])
    result = await svc.generate("prompt")
    assert result == "fallback"
    assert a.generate_calls == 1
    assert b.generate_calls == 1


@pytest.mark.asyncio
async def test_generate_raises_if_all_services_fail():
    a = _FakeService(generate_exc=RuntimeError("down a"))
    b = _FakeService(generate_exc=RuntimeError("down b"))
    svc = FailoverLLMService([a, b])
    with pytest.raises(RuntimeError, match="down b"):
        await svc.generate("prompt")


@pytest.mark.asyncio
async def test_stream_fails_over_before_any_token_yielded():
    a = _FakeService(stream_tokens=[], stream_exc=RuntimeError("rate limited"), stream_exc_after=0)
    b = _FakeService(stream_tokens=["hi", " there"])
    svc = FailoverLLMService([a, b])
    tokens = [t async for t in svc.stream_generate("prompt")]
    assert tokens == ["hi", " there"]


@pytest.mark.asyncio
async def test_stream_does_not_fail_over_mid_stream():
    a = _FakeService(stream_tokens=["partial"], stream_exc=RuntimeError("dropped"), stream_exc_after=1)
    b = _FakeService(stream_tokens=["should", "not", "be", "used"])
    svc = FailoverLLMService([a, b])
    with pytest.raises(RuntimeError, match="dropped"):
        async for _ in svc.stream_generate("prompt"):
            pass
    assert b.stream_calls == 0


@pytest.mark.asyncio
async def test_health_check_true_if_any_service_healthy():
    a = _FakeService(health=False)
    b = _FakeService(health=True)
    svc = FailoverLLMService([a, b])
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_false_if_all_unhealthy():
    a = _FakeService(health=False)
    b = _FakeService(health=False)
    svc = FailoverLLMService([a, b])
    assert await svc.health_check() is False
