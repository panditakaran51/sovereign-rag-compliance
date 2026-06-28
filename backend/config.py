from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen3.6:27b"
    ollama_rewrite_model: str = "qwen3:30b-a3b"
    ollama_embed_model: str = "nomic-embed-text"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "regulations"

    # RAG behaviour
    chunk_size: int = 512
    chunk_overlap: int = 64
    retrieval_top_k: int = 6
    confidence_threshold: int = 3
    bm25_corpus_path: str = "data/bm25_corpus.json"

    # Logging
    log_level: str = "info"


settings = Settings()
