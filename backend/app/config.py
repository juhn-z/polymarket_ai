"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./polypredict.db"
    admin_api_key: str = "change_me_in_production"

    polymarket_gamma_api_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_api_url: str = "https://clob.polymarket.com"
    polymarket_api_key: str = ""
    polymarket_api_secret: str = ""
    polymarket_passphrase: str = ""

    binance_api_url: str = "https://api.binance.com"
    fear_greed_api_url: str = "https://api.alternative.me/fng/"
    cryptopanic_api_url: str = "https://cryptopanic.com/api/v1/"
    cryptopanic_api_key: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-5.4"
    # OpenAI-compatible base URL. Override to use a proxy such as AIHubMix
    # (https://aihubmix.com/v1) without touching the adapter code.
    openai_base_url: str = "https://api.openai.com/v1"

    # Trade gate (PRD §3.4 = 0.25). Env-overridable so demos can run at a
    # lower threshold reflecting what the blind/decisive prompt naturally
    # produces; keep 0.25 in production.
    min_edge: Decimal = Decimal("0.25")

    polygon_rpc_url: str = ""
    admin_private_key: str = ""
    vault_contract_address: str = ""
    usdc_contract_address: str = ""

    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
