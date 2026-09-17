import uuid
from qdrant_client import models
from app.config import settings
from app.core.vectorstore import qdrant
from app.core.embeddings import embedder

CACHE_COLLECTION = settings.collection_name + "_semcache"
counters = {"hits": 0, "misses": 0}   # process-local; fine for demo, note in README

def _ensure():
    if not qdrant.collection_exists(CACHE_COLLECTION):
        qdrant.create_collection(
            collection_name=CACHE_COLLECTION,
            vectors_config=models.VectorParams(size=embedder.dim, distance=models.Distance.COSINE))

def get(query: str, tenant_id: str, role: str) -> dict | None:
    if not settings.cache_enabled:
        return None
    try:
        _ensure()
        vec = embedder.embed([query])[0]
        hits = qdrant.query_points(
            collection_name=CACHE_COLLECTION, query=vec,
            query_filter=models.Filter(must=[
                models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
                models.FieldCondition(key="role", match=models.MatchValue(value=role)),
            ]), limit=1).points
        if hits and hits[0].score >= settings.cache_threshold:
            counters["hits"] += 1
            payload = dict(hits[0].payload)
            payload["cache_score"] = round(hits[0].score, 4)
            return payload
        if hits and hits[0].score >= settings.cache_threshold - 0.07:
            print(f"[cache] near miss ({hits[0].score:.3f}): {hits[0].payload.get('query')!r}")
        counters["misses"] += 1
        return None
    except Exception:
        return None  # the cache must never break the request path

def put(query: str, answer: str, intent, citations: list, tenant_id: str, role: str):
    if not settings.cache_enabled:
        return
    try:
        _ensure()
        if qdrant.count(CACHE_COLLECTION, exact=True).count >= settings.cache_max_entries:
            return  # naive cap; prod would use LRU/TTL eviction
        vec = embedder.embed([query])[0]
        # deterministic uuid5 => identical queries overwrite instead of duplicating
        pid = uuid.uuid5(uuid.NAMESPACE_URL, f"{tenant_id}|{role}|{query}")
        qdrant.upsert(collection_name=CACHE_COLLECTION, points=[models.PointStruct(
            id=str(pid), vector=vec,
            payload={"query": query, "answer": answer, "intent": intent,
                     "citations": citations, "tenant_id": tenant_id, "role": role})])
    except Exception:
        pass

def invalidate():
    """Called on re-ingest: cached answers may reference outdated documents."""
    global counters
    counters = {"hits": 0, "misses": 0}
    try:
        if qdrant.collection_exists(CACHE_COLLECTION):
            qdrant.delete_collection(CACHE_COLLECTION)
    except Exception:
        pass