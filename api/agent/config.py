from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
import os


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    solar_model: str
    solar_api_key: str | None
    solar_base_url: str
    openai_api_key: str | None
    tavily_api_key: str | None


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "solar").lower(),
        solar_model=os.getenv("SOLAR_MODEL", "solar-pro"),
        solar_api_key=os.getenv("SOLAR_API_KEY"),
        solar_base_url=os.getenv("SOLAR_BASE_URL", "https://api.upstage.ai/v1"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        tavily_api_key=os.getenv("TAVILY_API_KEY"),
    )


def validate_settings(settings: Settings) -> list[str]:
    logger = logging.getLogger("visaguide.config")
    issues: list[str] = []

    if settings.llm_provider not in {"solar", "openai"}:
        issues.append(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

    if settings.llm_provider == "solar" and not settings.solar_api_key:
        issues.append("SOLAR_API_KEY is missing")
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        issues.append("OPENAI_API_KEY is missing")

    if settings.tavily_api_key and settings.tavily_api_key.startswith("tvly-..."):
        issues.append("TAVILY_API_KEY is a placeholder")

    for issue in issues:
        logger.warning(issue)

    return issues
