from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_url: str = "postgresql://sanctions:sanctions_pass@postgres:5432/sanctions_db"
    redis_url: str = "redis://redis:6379"
    celery_broker_url: str = "redis://redis:6379/1"
    elasticsearch_url: str = "http://elasticsearch:9200"
    notification_service_url: str = "http://notification-service:8007"

    ofac_sdn_url: str = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    ofsi_url: str = "https://ofsistorage.blob.core.windows.net/publishlive/ConList.csv"
    eu_consolidated_url: str = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList/content"
    un_consolidated_url: str = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
    opensanctions_pep_url: str = "https://data.opensanctions.org/datasets/latest/peps/targets.nested.json"

    sanctions_index_alias: str = "sanctions_entities"

    # Never serve data older than this without alerting (Section CC-07).
    max_staleness_hours: int = 48
    # Reject a sync if the new entry count is below this fraction of the
    # previous count — indicates a parsing error, not a real list shrink.
    min_entry_count_ratio: float = 0.95

    class Config:
        env_file = ".env"


settings = Settings()
