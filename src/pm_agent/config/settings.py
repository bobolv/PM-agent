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
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(default="sqlite:///./data/pm_agent.db", alias="DATABASE_URL")
    document_storage_path: str = Field(default="./data/documents", alias="DOCUMENT_STORAGE_PATH")
    template_library_path: str = Field(default="./template-library", alias="TEMPLATE_LIBRARY_PATH")
    llm_provider: Literal["openai", "volcengine", "openai_compatible"] = Field(
        default="openai",
        alias="LLM_PROVIDER",
    )
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    volcengine_base_url: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        alias="VOLCENGINE_BASE_URL",
    )
    volcengine_model: str = Field(
        default="doubao-seed-2-1-pro-260628",
        alias="VOLCENGINE_MODEL",
    )
    volcengine_api_key: str | None = Field(default=None, alias="VOLCENGINE_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
OPENAI_DEFAULT_MODEL = "gpt-4.1-mini"


def get_llm_base_url(settings: Settings) -> str:
    if settings.llm_provider == "volcengine" and settings.llm_base_url == OPENAI_DEFAULT_BASE_URL:
        return settings.volcengine_base_url
    return settings.llm_base_url


def get_llm_model(settings: Settings) -> str:
    if settings.llm_provider == "volcengine" and settings.llm_model == OPENAI_DEFAULT_MODEL:
        return settings.volcengine_model
    return settings.llm_model


def get_llm_api_key(settings: Settings) -> str | None:
    if settings.llm_provider == "volcengine":
        return settings.volcengine_api_key
    return settings.openai_api_key
