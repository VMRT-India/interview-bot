"""One-shot pre-generation of company-specific knowledge bases (Phase 7).

Reuses the exact JD-synthesis pipeline built for live JD-driven sessions
(services/jd_service.py's LLMKnowledgeProvider + services/company_lookup_service.py's
Tavily lookup) against a fixed company registry (services/company_registry.py) instead
of waiting on a real user-submitted JD. Real sessions where the parsed company_name
matches a registry entry (services.rag_service.retrieve()'s company_slug fallback tier)
get instant static hits instead of waiting on live per-session generation.

Idempotent: skips any company whose slug is already indexed in Qdrant.

Usage:
    python scripts/generate_company_kb.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import structlog

from services.company_registry import COMPANY_ARCHETYPES
from services.jd_service import knowledge_provider
from services.rag_service import rag_service

logger = structlog.get_logger()


async def main() -> None:
    for slug, jd_parsed in COMPANY_ARCHETYPES.items():
        log = logger.bind(company=jd_parsed.company_name, slug=slug)

        if await rag_service.has_jd_documents(slug):
            log.info("company_kb_already_indexed")
            continue

        log.info("company_kb_generating")
        docs = await knowledge_provider.generate(jd_parsed)
        if not docs:
            log.warning("company_kb_generation_empty")
            continue

        count = await rag_service.ingest_jd_documents(slug, docs, jd_parsed.domain)
        log.info("company_kb_ingested", count=count)


if __name__ == "__main__":
    asyncio.run(main())
