from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import settings
from services.company_lookup_service import company_lookup_service


def _mock_tavily_response(results: list[dict]):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"results": results})
    return resp


def _mock_async_client(response):
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


@pytest.mark.asyncio
async def test_search_interview_duration_returns_none_without_company_name():
    result = await company_lookup_service.search_interview_duration("")
    assert result is None


@pytest.mark.asyncio
async def test_search_interview_duration_returns_none_without_tavily_key():
    with patch.object(settings, "tavily_api_key", ""):
        result = await company_lookup_service.search_interview_duration("Acme")
    assert result is None


@pytest.mark.asyncio
async def test_search_interview_duration_extracts_minutes():
    response = _mock_tavily_response(
        [{"content": "Acme's technical interview typically runs 45-60 minutes."}]
    )
    with (
        patch.object(settings, "tavily_api_key", "fake-key"),
        patch("httpx.AsyncClient", new=_mock_async_client(response)),
        patch(
            "services.company_lookup_service.llm_service.generate",
            new=AsyncMock(return_value='{"minutes": 50}'),
        ),
    ):
        result = await company_lookup_service.search_interview_duration("Acme", "Backend Engineer")
    assert result == 50


@pytest.mark.asyncio
async def test_search_interview_duration_returns_none_when_no_snippets():
    response = _mock_tavily_response([])
    with (
        patch.object(settings, "tavily_api_key", "fake-key"),
        patch("httpx.AsyncClient", new=_mock_async_client(response)),
    ):
        result = await company_lookup_service.search_interview_duration("Acme")
    assert result is None


@pytest.mark.asyncio
async def test_search_interview_duration_returns_none_on_llm_failure():
    response = _mock_tavily_response([{"content": "Some unrelated content."}])
    with (
        patch.object(settings, "tavily_api_key", "fake-key"),
        patch("httpx.AsyncClient", new=_mock_async_client(response)),
        patch(
            "services.company_lookup_service.llm_service.generate",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        result = await company_lookup_service.search_interview_duration("Acme")
    assert result is None
