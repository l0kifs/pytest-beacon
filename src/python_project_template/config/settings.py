from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Configuration settings.
    """
    model_config = SettingsConfigDict(
        env_prefix="PYTHON_PROJECT_TEMPLATE__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="python-project-template", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")


def get_settings() -> Settings:
    """
    Get configuration settings.
    """
    return Settings()
