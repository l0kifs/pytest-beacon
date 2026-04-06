from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration settings.
    """
    model_config = SettingsConfigDict(
        env_prefix="PYTEST_BEACON__",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="pytest-beacon", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")

    # Plugin activation (can also be set via env var as fallback)
    generate_report: bool = Field(default=False, description="Enable beacon reporting (overridden by --beacon CLI flag)")

    # Output targets
    report_file: str | None = Field(default=None, description="Output file path (--beacon-file)")
    report_url: str | None = Field(default=None, description="Remote HTTP endpoint URL (--beacon-url)")
    report_format: str = Field(default="json", description="Report format: json or yaml (--beacon-format)")

    # Content control
    verbose: bool = Field(default=False, description="Include stdout/stderr for passed tests (--beacon-verbose)")
    exclude_statuses: str = Field(
        default="passed",
        description="Comma-separated test statuses to exclude from report output (--beacon-exclude-status)",
    )

    # HTTP export settings
    http_timeout: float = Field(default=10.0, description="HTTP export request timeout in seconds")
    http_max_retries: int = Field(default=3, description="HTTP export maximum retry attempts")


def get_settings() -> Settings:
    """
    Get configuration settings.
    """
    return Settings()
