from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Behavioral Drift API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/behavioral_drift"
    secret_key: str = "change-me"

    # Drift detection thresholds
    min_baseline_sessions: int = 5       # sessions needed before drift fires
    baseline_window: int = 30            # rolling window of sessions for baseline
    drift_z_threshold: float = 2.0       # z-score to flag individual metric
    drift_score_threshold: float = 1.5   # weighted score to fire drift event

    # Webhook delivery
    webhook_timeout_s: int = 10
    webhook_max_retries: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
