from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_url: str = "postgresql://sanctions:sanctions_pass@postgres:5432/sanctions_db"
    redis_url: str = "redis://redis:6379"
    notification_service_url: str = "http://notification-service:8007"
    audit_trail_url: str = "http://audit-trail:8000"

    # Section 6.2 — Track B high-priority threshold.
    high_priority_threshold: float = 0.85

    # SLA windows (hours). High-priority items get a tighter window.
    standard_sla_hours: float = 24.0
    high_priority_sla_hours: float = 4.0

    # Section 6.4 EscalationEngine — network risk >= this raises queue
    # priority without changing the verdict class (still REVIEW).
    network_priority_boost_threshold: float = 0.70

    class Config:
        env_file = ".env"


settings = Settings()
