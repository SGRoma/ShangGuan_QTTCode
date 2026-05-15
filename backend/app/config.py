from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AIQuant Platform"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./data/aiquant.db"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    default_stock: str = "600418"
    market_data_source: str = "eastmoney"
    bltcy_name: str = "BLTCY"
    bltcy_base_url: str = "https://api.bltcy.ai/v1"
    bltcy_api_key: str | None = None
    bltcy_wire_api: str = "responses"
    bltcy_model: str = "gpt-5"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.database_url.startswith("sqlite:///./"):
        db_path = Path(settings.database_url.replace("sqlite:///./", "", 1))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
