from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # --- llm providers (all speak the OpenAI protocol; swap via env only) ---
    llm_provider: str = "gemini"          # gemini | groq | openai | openrouter | ollama
    llm_model: str = "gemini-2.0-flash"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""

    # judge defaults to the main provider unless overridden
    judge_provider: str = ""              # e.g. "groq" — judge on a *different* model
    judge_model: str = ""                 # e.g. "llama-3.3-70b-versatile"

    # --- embeddings ---
    embedding_provider: str = "local"     # local (sentence-transformers) | remote
    embedding_model_local: str = "BAAI/bge-small-en-v1.5"
    embedding_model_remote: str = "text-embedding-3-small"

    qdrant_url: str = "http://localhost:6333"
    database_url: str = "sqlite:///./supportops.db"
    collection_name: str = "knowledge"

    # --- retrieval (unchanged from week 2) ---
    retrieval_mode: str = "hybrid"
    chunk_words: int = 250
    chunk_overlap_words: int = 50
    retrieval_k: int = 30
    rerank_pool: int = 20
    final_k: int = 5

    # --- reranking ---
    rerank_provider: str = "local"        # none | local | cohere
    cohere_api_key: str = ""
    rerank_model_local: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_model_cohere: str = "rerank-v3.5"

    query_rewrite_enabled: bool = True

settings = Settings()