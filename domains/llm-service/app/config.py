from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_timeout_seconds: float = 60.0

    class Config:
        env_file = ".env"


settings = Settings()
