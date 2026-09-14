from app.config import settings

class LocalEmbedder:
    """CPU, no API, no rate limits. ~90MB model download on first use.
    bge-small-en-v1.5: 384-dim, punches far above its size."""
    name = "local"

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self._dim = self.model.get_sentence_embedding_dimension()

    @property
    def dim(self): return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()

class RemoteEmbedder:
    """OpenAI-protocol embeddings endpoint — for if you later get credits."""
    name = "remote"

    def __init__(self, model: str, api_key: str, base_url: str = "https://api.openai.com/v1"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self._dim = None

    @property
    def dim(self):
        if self._dim is None:
            self._dim = len(self.embed(["dim probe"])[0])
        return self._dim

    def embed(self, texts):
        out = []
        for i in range(0, len(texts), 100):
            resp = self.client.embeddings.create(model=self.model, input=texts[i:i+100])
            out.extend(d.embedding for d in resp.data)
        return out

def make_embedder():
    if settings.embedding_provider == "remote":
        return RemoteEmbedder(settings.embedding_model_remote, settings.openai_api_key)
    return LocalEmbedder(settings.embedding_model_local)

embedder = make_embedder()