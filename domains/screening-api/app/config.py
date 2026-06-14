from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    entity_resolution_url: str = "http://entity-resolution:8002"
    graph_engine_url: str = "http://graph-engine:8005"
    regulatory_engine_url: str = "http://regulatory-engine:8003"
    crypto_screener_url: str = "http://crypto-screener:8004"
    llm_service_url: str = "http://llm-service:8006"
    audit_trail_url: str = "http://audit-trail:8008"
    review_queue_url: str = "http://review-queue:8009"
    redis_url: str = "redis://redis:6379"
    postgres_url: str = "postgresql://sanctions:sanctions_pass@postgres:5432/sanctions_db"

    class Config:
        env_file = ".env"


settings = Settings()
