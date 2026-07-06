import asyncio

from fastapi import APIRouter
from sqlalchemy import text

from db.mongo import get_client as get_mongo_client
from db.postgres import AsyncSessionFactory
from db.qdrant import get_qdrant
from db.redis import get_redis
from models.schemas.health import HealthResponse, ServiceHealth
from services.llm_service import llm_service

router = APIRouter()


async def _check_postgres() -> ServiceHealth:
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return ServiceHealth(status="ok")
    except Exception as e:
        return ServiceHealth(status="error", detail=str(e))


async def _check_mongo() -> ServiceHealth:
    try:
        await get_mongo_client().admin.command("ping")
        return ServiceHealth(status="ok")
    except Exception as e:
        return ServiceHealth(status="error", detail=str(e))


async def _check_redis() -> ServiceHealth:
    try:
        await get_redis().ping()
        return ServiceHealth(status="ok")
    except Exception as e:
        return ServiceHealth(status="error", detail=str(e))


async def _check_ollama() -> ServiceHealth:
    ok = await llm_service.health_check()
    return ServiceHealth(status="ok") if ok else ServiceHealth(status="error", detail="ollama unreachable")


async def _check_qdrant() -> ServiceHealth:
    try:
        await get_qdrant().get_collections()
        return ServiceHealth(status="ok")
    except Exception as e:
        return ServiceHealth(status="error", detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    results = await asyncio.gather(
        _check_postgres(),
        _check_mongo(),
        _check_redis(),
        _check_ollama(),
        _check_qdrant(),
        return_exceptions=True,
    )

    labels = ["postgres", "mongo", "redis", "ollama", "qdrant"]
    services: dict[str, ServiceHealth] = {}
    for label, result in zip(labels, results):
        if isinstance(result, Exception):
            services[label] = ServiceHealth(status="error", detail=str(result))
        else:
            services[label] = result

    overall = "ok" if all(s.status == "ok" for s in services.values()) else "degraded"
    return HealthResponse(status=overall, services=services)
