from qdrant_client import QdrantClient, models
from app.config import settings
from app.core.embeddings import embedder

qdrant = QdrantClient(url=settings.qdrant_url)

def ensure_collection():
    if qdrant.collection_exists(settings.collection_name):
        info = qdrant.get_collection(settings.collection_name)
        if info.config.params.vectors.size != embedder.dim:
            print(f"[vectorstore] embedding dim changed "
                  f"({info.config.params.vectors.size} -> {embedder.dim}); "
                  f"recreating collection — re-ingest your documents")
            qdrant.delete_collection(settings.collection_name)
    if not qdrant.collection_exists(settings.collection_name):
        qdrant.create_collection(
            collection_name=settings.collection_name,
            vectors_config=models.VectorParams(size=embedder.dim, distance=models.Distance.COSINE),
        )