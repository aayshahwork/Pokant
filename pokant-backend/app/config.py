from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://localhost:5432/pokant"
    secret_key: str = "dev-secret-key-change-in-production"
    encryption_key: str = ""
    vapi_test_api_key: str = ""
    claude_api_key: str = ""
    openai_api_key: str = ""
    environment: str = "development"
    debug: bool = True
    redis_url: str = "redis://localhost:6379/0"

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
