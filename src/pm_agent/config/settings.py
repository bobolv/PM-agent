from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="pm-agent", alias="APP_NAME")
    app_env: Literal["development", "testing", "production"] = Field(
        default="development",
        alias="APP_ENV",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(default="sqlite:///./data/pm_agent.db", alias="DATABASE_URL")
    document_storage_path: str = Field(default="./data/documents", alias="DOCUMENT_STORAGE_PATH")
    template_library_path: str = Field(default="./template-library", alias="TEMPLATE_LIBRARY_PATH")
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
