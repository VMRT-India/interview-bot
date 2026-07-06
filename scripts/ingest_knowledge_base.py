"""
One-shot script: seeds MongoDB knowledge_base collection from data/knowledge_base_seed.json,
then embeds and indexes all documents into Qdrant.

Usage:
    python scripts/ingest_knowledge_base.py

Prerequisites:
    - Ollama running with `nomic-embed-text` pulled
    - MongoDB and Qdrant containers running
    - Run from the project root directory
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.mongo import close as close_mongo
from db.mongo import knowledge_base_col
from db.qdrant import COLLECTION_NAME, init_collection, get_qdrant
from services.embedding_service import get_embedding_service
from services.rag_service import rag_service

log = structlog.get_logger()

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "knowledge_base_seed.json"


async def _check_ollama_embedding() -> None:
    embedder = get_embedding_service()
    try:
        vec = await embedder.embed("health check")
        log.info("embedding_health_ok", dim=len(vec))
    except Exception as exc:
        log.error(
            "embedding_health_failed",
            error=str(exc),
            hint="Run: ollama pull nomic-embed-text",
        )
        sys.exit(1)


async def _seed_knowledge_base() -> int:
    if not SEED_FILE.exists():
        log.error("seed_file_not_found", path=str(SEED_FILE))
        sys.exit(1)

    with SEED_FILE.open() as f:
        documents = json.load(f)

    col = knowledge_base_col()
    seeded = 0
    for doc in documents:
        doc_id = str(uuid.uuid4())
        doc["doc_id"] = doc_id
        result = await col.update_one(
            {"question": doc["question"]},
            {"$setOnInsert": doc},
            upsert=True,
        )
        if result.upserted_id:
            seeded += 1

    log.info("kb_seed_complete", seeded=seeded, total=len(documents))
    return seeded


async def _reset_qdrant_collection() -> None:
    client = get_qdrant()
    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION_NAME in existing:
        await client.delete_collection(COLLECTION_NAME)
        log.info("qdrant_collection_deleted", collection=COLLECTION_NAME)
    await init_collection()
    log.info("qdrant_collection_created", collection=COLLECTION_NAME)


async def main() -> None:
    log.info("ingest_start")

    log.info("step_1_embedding_health_check")
    await _check_ollama_embedding()

    log.info("step_2_seed_mongodb")
    await _seed_knowledge_base()

    log.info("step_3_reset_qdrant_collection")
    await _reset_qdrant_collection()

    log.info("step_4_embed_and_index")
    inserted = await rag_service.ingest_knowledge_base()

    log.info("ingest_done", rows_inserted=inserted)
    await close_mongo()


if __name__ == "__main__":
    asyncio.run(main())
