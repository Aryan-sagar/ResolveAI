import re
from rank_bm25 import BM25Okapi
from qdrant_client import models
from app.config import settings
from app.core.vectorstore import qdrant
from app.core.embeddings import embedder
from app.db.session import SessionLocal
from app.db.models import Chunk, Document

def _tok(t): return re.findall(r"\w+", t.lower())

class HybridRetriever:
    def __init__(self):
        self._bm25, self._chunks = None, []

    def _build_index(self):
        db = SessionLocal()
        rows = db.query(Chunk, Document).join(Document, Chunk.document_id == Document.id).all()
        self._chunks = [{"qid": c.qdrant_id, "content": c.content, "source": d.source,
                         "doc_type": d.doc_type, "tenant_id": d.tenant_id,
                         "access_level": d.access_level} for c, d in rows]
        self._bm25 = BM25Okapi([_tok(c["content"]) for c in self._chunks]) if self._chunks else None
        db.close()

    def invalidate(self):
        self._bm25 = None

    def search(self, query, tenant_id, access_levels=("public",), k=None):
        if self._bm25 is None:
            self._build_index()
        k = k or settings.final_k

        # 1) vector search, filtered by tenant + access level (multi-tenancy lives here)
        filt = models.Filter(must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
            models.FieldCondition(key="access_level", match=models.MatchAny(any=list(access_levels))),
        ])
        meta, scores = {}, {}
        try:
            vec = embedder.embed([query])[0]
            hits = qdrant.query_points(collection_name=settings.collection_name, query=vec,
                                       query_filter=filt, limit=settings.retrieval_k).points
            for rank, h in enumerate(hits):
                scores[h.id] = scores.get(h.id, 0) + 1.0 / (60 + rank + 1)
                meta[h.id] = {**h.payload, "qid": str(h.id)}
        except Exception:
            pass  # no collection yet / qdrant down: fall back to BM25 only

        # 2) BM25 over tenant-accessible chunks (catches IDs, error codes, exact names)
        allowed = [i for i, c in enumerate(self._chunks)
                   if c["tenant_id"] == tenant_id and c["access_level"] in access_levels]
        if self._bm25 and allowed:
            bm_scores = self._bm25.get_scores(_tok(query))
            ranked = [i for i in sorted(allowed, key=lambda i: bm_scores[i], reverse=True)
                      if bm_scores[i] > 0][:settings.retrieval_k]
            for rank, i in enumerate(ranked):
                qid = self._chunks[i]["qid"]
                scores[qid] = scores.get(qid, 0) + 1.0 / (60 + rank + 1)
                meta.setdefault(qid, self._chunks[i])

        # 3) RRF fusion
        top = sorted(scores.items(), key=lambda x: -x[1])[:k]
        return [{**meta[qid], "score": round(s, 4)} for qid, s in top if qid in meta]

retriever = HybridRetriever()