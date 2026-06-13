from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_url: str = "postgresql://sanctions:sanctions_pass@postgres:5432/sanctions_db"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "sanctions_minio"
    minio_secret_key: str = "sanctions_minio_pass"
    minio_secure: bool = False
    minio_bucket: str = "audit-documents"

    class Config:
        env_file = ".env"


settings = Settings()
