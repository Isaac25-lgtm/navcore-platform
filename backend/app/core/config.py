from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NAVFund API"
    api_prefix: str = "/api/v1"
    debug: bool = False
    auto_create_schema: bool = True

    database_url: str = (
        "postgresql+psycopg2://navfund:navfund@localhost:5432/navfund"
    )
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    reports_dir: str = str(Path(__file__).resolve().parents[2] / "storage" / "reports")
    docs_dir: str = str(Path(__file__).resolve().parents[2] / "docs")
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    copilot_temperature: float = 0.2
    copilot_max_output_tokens: int = 900

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
