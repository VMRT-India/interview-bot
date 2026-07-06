import httpx
import structlog

from config import settings
from services.json_utils import extract_json
from services.llm_service import llm_service

logger = structlog.get_logger()

_TAVILY_URL = "https://api.tavily.com/search"

_DURATION_EXTRACT_SYSTEM = (
    "Extract a typical interview duration in minutes from the search snippets below. "
    'Return ONLY JSON: {"minutes": <integer> or null if no duration is mentioned or implied}. '
    "If a range is given (e.g. \"45-60 minutes\"), return the midpoint rounded to the nearest 5."
)


class CompanyLookupService:
    """Looks up real, current info about a company's interview process via Tavily search."""

    async def _search(self, query: str, max_results: int = 5) -> list[str]:
        if not settings.tavily_api_key:
            return []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    _TAVILY_URL,
                    json={
                        "api_key": settings.tavily_api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": max_results,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.warning("tavily_lookup_failed", query=query, error=str(exc))
            return []

        return [
            content[:500]
            for result in data.get("results", [])
            if (content := result.get("content", "").strip())
        ]

    async def search_interview_style(self, company_name: str) -> list[str]:
        if not company_name:
            return []
        query = f"{company_name} technical interview process questions rounds format"
        return await self._search(query)

    async def search_interview_duration(
        self, company_name: str, role_title: str | None = None
    ) -> int | None:
        """Best-effort: researches and extracts a typical interview length in minutes for a
        company/role. Returns None on no signal or any failure — caller falls back to
        `settings.default_interview_target_minutes`."""
        if not company_name:
            return None
        query = f"{company_name} {role_title or ''} interview duration typical length minutes".strip()
        snippets = await self._search(query, max_results=5)
        if not snippets:
            return None

        try:
            raw = await llm_service.generate(
                "\n---\n".join(snippets),
                system_prompt=_DURATION_EXTRACT_SYSTEM,
                json_mode=True,
            )
            minutes = extract_json(raw).get("minutes")
            return int(minutes) if isinstance(minutes, (int, float)) else None
        except Exception as exc:
            logger.warning("duration_extract_failed", company=company_name, error=str(exc))
            return None


company_lookup_service = CompanyLookupService()
