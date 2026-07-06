from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_url)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongo_db]


async def close():
    global _client
    if _client:
        _client.close()
        _client = None


# Collection accessors
def sessions_col():
    return get_db()["interview_sessions"]


def scraped_col():
    return get_db()["scraped_raw"]


def knowledge_base_col():
    return get_db()["knowledge_base"]


def session_reports_col():
    return get_db()["session_reports"]