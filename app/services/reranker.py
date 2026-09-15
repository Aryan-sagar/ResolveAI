from abc import ABC, abstractmethod
from app.config import settings

class BaseReranker(ABC):
    name = "base"

    @abstractmethod
    def rerank(self, query: str, docs: list[dict], top_k: int) -> list[dict]:
        """Reorder docs by relevance to query, return top_k. Docs carry 'content' + metadata."""

class NoopReranker(BaseReranker):
    """Keeps fused RRF order. The A/B baseline: measures what reranking adds."""
    name = "none"

    def rerank(self, query, docs, top_k):
        return docs[:top_k]

class CohereReranker(BaseReranker):
    name = "cohere"

    def __init__(self):
        import cohere
        self.client = cohere.Client(settings.cohere_api_key)
        self.model = settings.rerank_model_cohere

    def rerank(self, query, docs, top_k):
        resp = self.client.rerank(
            model=self.model, query=query,
            documents=[d["content"][:4000] for d in docs],  # API length safety
            top_n=top_k,
        )
        out = []
        for r in resp.results:
            d = dict(docs[r.index])
            d["rerank_score"] = round(r.relevance_score, 4)
            out.append(d)
        return out

class LocalReranker(BaseReranker):
    """Cross-encoder via sentence-transformers. Free + offline; model loads lazily
    so app startup stays fast. Upgrade path: BAAI/bge-reranker-v2-m3 (multilingual,
    notably better on Hinglish/mixed-language queries, slower on CPU)."""
    name = "local"

    def __init__(self):
        try:
            import sentence_transformers  # fail fast with a clear message
        except ImportError as e:
            raise ImportError(
                "RERANK_PROVIDER=local requires sentence-transformers. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from e
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(settings.rerank_model_local, max_length=512)
        return self._model

    def rerank(self, query, docs, top_k):
        scores = self.model.predict([(query, d["content"]) for d in docs])
        ranked = sorted(zip(docs, scores), key=lambda x: -x[1])[:top_k]
        out = []
        for d, s in ranked:
            d = dict(d)
            d["rerank_score"] = round(float(s), 4)
            out.append(d)
        return out

def make_reranker(provider: str | None = None) -> BaseReranker:
    provider = (provider or settings.rerank_provider).lower()
    if provider == "cohere":
        if not settings.cohere_api_key:
            print("WARNING: RERANK_PROVIDER=cohere but COHERE_API_KEY unset — falling back to none")
            return NoopReranker()
        return CohereReranker()
    if provider == "local":
        return LocalReranker()
    return NoopReranker()