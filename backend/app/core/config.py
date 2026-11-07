"""Application configuration.

All secrets are read from the environment (never from the frontend).
`RUNTIME_MODE` is derived, never fabricated: if live credentials are present
the platform reports LIVE, otherwise it reports SIMULATED and every UI surface
that depends on it says so explicitly.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- app -------------------------------------------------------------
    app_name: str = "EPOCH AI"
    api_v1_prefix: str = "/api/v1"
    environment: Literal["local", "staging", "production"] = "local"
    debug: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- database --------------------------------------------------------
    # SQLite is the zero-config default; set DATABASE_URL=postgresql+psycopg://...
    database_url: str = "sqlite:///./epoch.db"

    # ---- gateway (Bifrost by Maxim AI, OpenAI-compatible) ----------------
    bifrost_base_url: str = ""
    bifrost_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # model routing: primary reasoning model + cheap utility model + fallback
    model_primary: str = "openai/gpt-4o-mini"
    model_utility: str = "openai/gpt-4o-mini"
    model_fallback: str = "google/gemini-2.0-flash"
    llm_timeout_seconds: float = 45.0
    llm_max_retries: int = 2

    # ---- research provider ----------------------------------------------
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    tavily_timeout_seconds: float = 20.0
    tavily_max_results: int = 6
    research_max_claims: int = 12
    research_concurrency: int = 4

    # ---- pricing used for cost estimation (USD per 1K tokens) -----------
    # Defaults are conservative list prices; override via env for your contract.
    price_input_per_1k: float = 0.00015
    price_output_per_1k: float = 0.0006
    tavily_price_per_search: float = 0.008

    # ---- limits / security ----------------------------------------------
    max_input_chars: int = 20_000
    max_url_fetch_bytes: int = 2_000_000
    rate_limit_per_minute: int = 60
    allow_private_networks: bool = False  # SSRF guard; keep False in production
    job_timeout_seconds: float = 180.0

    # ---- derived ---------------------------------------------------------
    @property
    def live_llm(self) -> bool:
        return bool(self.bifrost_api_key or self.openai_api_key or self.gemini_api_key)

    @property
    def live_search(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def runtime_mode(self) -> Literal["live", "hybrid", "simulated"]:
        if self.live_llm and self.live_search:
            return "live"
        if self.live_llm or self.live_search:
            return "hybrid"
        return "simulated"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
