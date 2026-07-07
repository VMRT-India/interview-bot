from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_url: str = "postgresql+asyncpg://interview:interview@localhost:5432/interview_bot"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "interview_bot"
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"

    ollama_host: str = "http://localhost:11434"
    ollama_timeout: int = 120

    # LLM provider: "groq" | "gemini" | "mlx"
    llm_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    llm_base_url: str = "http://localhost:__MLX_PORT__/v1"
    llm_model_name: str = "local-model"

    # App-default Gemini (llm_provider="gemini") — two keys supported for load
    # spreading across separate free-tier rate limits; gemini_api_key_2 is optional,
    # failover only kicks in on a request failure (not round-robin).
    # gemini-2.5-flash-lite is deliberately the cheapest current Gemini model
    # ($0.10/$0.40 per 1M tokens) rather than a newer, pricier Flash-Lite generation.
    gemini_api_key: str = ""
    gemini_api_key_2: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"

    tavily_api_key: str = ""

    # "ollama" (local daemon) | "huggingface" (HF's free Inference API, Ollama kept as fallback)
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    hf_api_token: str = ""
    # bge-base, not nomic — nomic-embed-text-v1.5 has no live HF inference provider
    # (verified live: empty inferenceProviderMapping), bge-base is 768-dim and live
    hf_embedding_model: str = "BAAI/bge-base-en-v1.5"

    log_level: str = "INFO"
    # Absolute last-resort circuit breaker, not the normal termination path (Phase 8 —
    # interview length is time/judgment-driven; see default_interview_target_minutes below)
    max_interview_turns: int = 40

    # Phase 8 — adaptive interview length
    default_interview_target_minutes: int = 45
    # Point past target_minutes at which closing becomes mandatory rather than an LLM
    # judgment call (the user's "25-30% additional")
    interview_overrun_factor: float = 1.3

    # Auth
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # BYOK — Fernet key encrypting user-supplied LLM API keys at rest
    encryption_master_key: str = ""

    # OAuth (Phase 7) — set once app registered with each provider
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"
    # {provider} placeholder. Default matches this backend's own callback route
    # (/auth/{provider}/callback) for direct-backend testing. Point this at the
    # frontend's actual route (/oauth/callback/{provider}) once oauth_redirect_base_url
    # is set to the frontend origin, so Google/GitHub redirect somewhere the SPA router
    # actually handles.
    oauth_callback_path_template: str = "/auth/{provider}/callback"

    # Frontend dev/prod origin(s) allowed to call this API directly (CORS)
    cors_allowed_origins: list[str] = ["http://localhost:5173"]


settings = Settings()