from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    ENVIRONMENT: str = "development"
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/computeruse"
    ANTHROPIC_API_KEY: str = ""
    BROWSERBASE_API_KEY: str = ""
    BROWSERBASE_PROJECT_ID: str = ""
    R2_ACCESS_KEY: str = ""
    R2_SECRET_KEY: str = ""
    R2_BUCKET_NAME: str = "computeruse-recordings"
    R2_ENDPOINT: str = ""
    TWOCAPTCHA_API_KEY: str = ""
    ENCRYPTION_MASTER_KEY: str = "change-me"
    CANARY_DEPLOYMENT: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


worker_settings = WorkerSettings()


_r2_checked: bool | None = None


def is_r2_configured() -> bool:
    """Return True if R2 credentials and endpoint are valid and boto3 accepts them.

    Result is cached after the first call so we only log the warning once.
    """
    global _r2_checked
    if _r2_checked is not None:
        return _r2_checked

    key = worker_settings.R2_ACCESS_KEY
    secret = worker_settings.R2_SECRET_KEY
    endpoint = worker_settings.R2_ENDPOINT

    # Quick checks for missing / placeholder values
    if not (key and secret and endpoint):
        _r2_checked = False
        return False
    placeholders = {"your_r2_access_key", "your_r2_secret_key", "your_r2_endpoint", "xxx", "XXXXX"}
    if key in placeholders or secret in placeholders:
        _r2_checked = False
        return False
    if "xxx" in endpoint or "your_" in endpoint or "ACCOUNT_ID" in endpoint:
        _r2_checked = False
        return False

    # Definitive check: boto3 validates the endpoint URL at client creation
    try:
        import boto3
        boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
        )
        _r2_checked = True
    except Exception:
        import logging
        logging.getLogger("pokant.config").warning(
            "R2 not configured: boto3 rejected endpoint_url=%s — skipping all R2 uploads",
            endpoint,
        )
        _r2_checked = False

    return _r2_checked
