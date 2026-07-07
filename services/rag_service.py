import uuid

import structlog
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

from db.mongo import knowledge_base_col
from db.qdrant import COLLECTION_NAME, get_qdrant
from services.embedding_service import EmbeddingProvider, get_embedding_service

logger = structlog.get_logger()

_COSINE_WEIGHT = 0.7
_L2_WEIGHT = 0.3
_OVERSAMPLE = 5
_STATIC_HASH = "static"
_UPSERT_BATCH_SIZE = 100


class RAGService:
    def __init__(self) -> None:
        self._embedder: EmbeddingProvider = get_embedding_service()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        domain: str,
        top_k: int = 3,
        jd_hash: str | None = None,
        company_slug: str | None = None,
    ) -> list[str]:
        try:
            query_vec = await self._embedder.embed(query)
        except Exception as exc:
            logger.warning("rag_embed_failed", error=str(exc))
            logger.info("rag_retrieve_metric", domain=domain, hit=False, chunk_count=0, source="embed_failed")
            return []

        # Prefer exact-JD-specific knowledge, then pre-generated company KB, then static
        if jd_hash:
            results = await self._search_by_hash(query_vec, domain, top_k, jd_hash)
            if results:
                logger.info(
                    "rag_retrieve_metric", domain=domain, hit=True, chunk_count=len(results), source="jd"
                )
                return results

        if company_slug:
            results = await self._search_by_hash(query_vec, domain, top_k, company_slug)
            if results:
                logger.info(
                    "rag_retrieve_metric",
                    domain=domain,
                    hit=True,
                    chunk_count=len(results),
                    source="company",
                )
                return results

        results = await self._search_by_hash(query_vec, domain, top_k, _STATIC_HASH)
        logger.info(
            "rag_retrieve_metric",
            domain=domain,
            hit=bool(results),
            chunk_count=len(results),
            source="static",
        )
        return results

    async def _search_by_hash(
        self,
        query_vec: list[float],
        domain: str,
        top_k: int,
        jd_hash: str,
    ) -> list[str]:
        try:
            client = get_qdrant()
            limit = top_k * _OVERSAMPLE
            search_filter = Filter(
                must=[
                    FieldCondition(key="domain", match=MatchValue(value=domain)),
                    FieldCondition(key="jd_hash", match=MatchValue(value=jd_hash)),
                ]
            )

            cosine_hits, euclid_hits = await _dual_search(
                client, query_vec, search_filter, limit
            )

            cosine_map = {str(h.id): h.score for h in cosine_hits}
            euclid_map = {str(h.id): h.score for h in euclid_hits}
            all_ids = set(cosine_map) | set(euclid_map)

            combined: dict[str, float] = {}
            for pid in all_ids:
                cs = cosine_map.get(pid, 0.0)
                es = euclid_map.get(pid, None)
                l2_dist = -es if es is not None else 1e6
                eu_sim = 1.0 / (1.0 + l2_dist)
                combined[pid] = _COSINE_WEIGHT * cs + _L2_WEIGHT * eu_sim

            top_ids = sorted(combined, key=combined.__getitem__, reverse=True)[:top_k]

            payload_map: dict[str, dict] = {}
            for hit in cosine_hits + euclid_hits:
                pid = str(hit.id)
                if pid not in payload_map and hit.payload:
                    payload_map[pid] = hit.payload

            return [
                payload_map[pid]["text"]
                for pid in top_ids
                if pid in payload_map and "text" in payload_map[pid]
            ]

        except Exception as exc:
            logger.warning("rag_retrieve_failed", jd_hash=jd_hash, error=str(exc))
            return []

    # ------------------------------------------------------------------
    # JD knowledge
    # ------------------------------------------------------------------

    async def has_jd_documents(self, jd_hash: str) -> bool:
        try:
            client = get_qdrant()
            points, _ = await client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[FieldCondition(key="jd_hash", match=MatchValue(value=jd_hash))]
                ),
                limit=1,
                with_payload=False,
            )
            return bool(points)
        except Exception as exc:
            logger.warning("rag_has_jd_docs_failed", jd_hash=jd_hash, error=str(exc))
            return False

    async def ingest_jd_documents(
        self, jd_hash: str, documents: list[dict], domain: str
    ) -> int:
        client = get_qdrant()
        points: list[PointStruct] = []

        for doc in documents:
            chunk_text = _build_chunk(doc)
            try:
                vector = await self._embedder.embed(chunk_text)
            except Exception as exc:
                logger.warning("rag_jd_embed_failed", error=str(exc))
                continue

            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector={"cosine": vector, "euclid": vector},
                    payload={
                        "domain": domain,
                        "topic": doc.get("topic", ""),
                        "difficulty": doc.get("difficulty", 2),
                        "tags": [],
                        "text": chunk_text,
                        "source_id": str(uuid.uuid4()),
                        "jd_hash": jd_hash,
                    },
                )
            )

        if points:
            await client.upsert(collection_name=COLLECTION_NAME, points=points)

        logger.info("rag_jd_ingest_complete", jd_hash=jd_hash, count=len(points))
        return len(points)

    # ------------------------------------------------------------------
    # Static knowledge base ingestion
    # ------------------------------------------------------------------

    async def ingest_knowledge_base(self) -> int:
        col = knowledge_base_col()
        docs = await col.find({}).to_list(length=None)
        if not docs:
            logger.warning("rag_ingest_no_docs")
            return 0

        client = get_qdrant()
        points: list[PointStruct] = []

        for doc in docs:
            doc_id_raw = doc.get("doc_id")
            if not doc_id_raw:
                logger.warning("rag_ingest_missing_doc_id", doc=str(doc.get("_id")))
                continue

            chunk_text = _build_chunk(doc)
            try:
                vector = await self._embedder.embed(chunk_text)
            except Exception as exc:
                logger.warning("rag_ingest_embed_failed", doc_id=doc_id_raw, error=str(exc))
                continue

            points.append(
                PointStruct(
                    id=doc_id_raw,
                    vector={"cosine": vector, "euclid": vector},
                    payload={
                        "domain": doc.get("domain", ""),
                        "topic": doc.get("topic", ""),
                        "difficulty": doc.get("difficulty", 1),
                        "tags": doc.get("tags", []),
                        "text": chunk_text,
                        "source_id": doc_id_raw,
                        "jd_hash": _STATIC_HASH,
                    },
                )
            )

        for i in range(0, len(points), _UPSERT_BATCH_SIZE):
            batch = points[i : i + _UPSERT_BATCH_SIZE]
            await client.upsert(collection_name=COLLECTION_NAME, points=batch)

        logger.info("rag_ingest_complete", inserted=len(points), total=len(docs))
        return len(points)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

async def _dual_search(client, query_vec, search_filter, limit):
    import asyncio
    cosine_task = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        using="cosine",
        query_filter=search_filter,
        limit=limit,
        with_payload=True,
    )
    euclid_task = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vec,
        using="euclid",
        query_filter=search_filter,
        limit=limit,
        with_payload=True,
    )
    cosine_resp, euclid_resp = await asyncio.gather(cosine_task, euclid_task)
    return cosine_resp.points, euclid_resp.points


def _build_chunk(doc: dict) -> str:
    return f"Q: {doc.get('question', '')}\nA: {doc.get('ideal_answer', '')}"


rag_service = RAGService()
