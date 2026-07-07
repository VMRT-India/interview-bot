from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from config import settings

COLLECTION_NAME = "knowledge_base"
VECTOR_DIM = 768

_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=60,
        )
    return _client


async def init_collection() -> None:
    client = get_qdrant()
    result = await client.get_collections()
    existing = {c.name for c in result.collections}
    if COLLECTION_NAME not in existing:
        await client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "cosine": VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
                "euclid": VectorParams(size=VECTOR_DIM, distance=Distance.EUCLID),
            },
        )


async def close() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None
