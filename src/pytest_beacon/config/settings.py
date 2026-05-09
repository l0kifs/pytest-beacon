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
    app_version: str = Field(default="0.5.0", description="Application version")

    # Plugin activation (can also be set via env var as fallback)
    generate_report: bool = Field(default=False, description="Enable beacon reporting (overridden by --beacon CLI flag)")

    # Output targets
    report_file: str | None = Field(default=None, description="Output file path (--beacon-file)")
    report_url: str | None = Field(default=None, description="Remote HTTP endpoint URL (--beacon-url)")
    report_format: str = Field(default="json", description="Report format: json or yaml (--beacon-format)")

    # Content control
    verbose: bool = Field(default=False, description="Include stdout/stderr for passed tests (--beacon-verbose)")
    file_exclude_statuses: str = Field(
        default="passed",
        description="Comma-separated test statuses to exclude from file report output (--beacon-file-exclude-status)",
    )
    http_exclude_statuses: str = Field(
        default="passed",
        description="Comma-separated test statuses to exclude from HTTP export (--beacon-http-exclude-status)",
    )

    # HTTP export settings
    http_timeout: float = Field(default=10.0, description="HTTP export request timeout in seconds")
    http_max_retries: int = Field(default=3, description="HTTP export maximum retry attempts")

    # Log capture settings
    logs_enabled: bool = Field(default=False, description="Enable log capture in reports (--beacon-logs)")
    logs_level: str = Field(default="WARNING", description="Minimum log level to capture (--beacon-logs-level)")
    logs_max_per_category: int | None = Field(
        default=None,
        description="Max log entries per phase category per test and for general logs (--beacon-logs-max)",
    )

    # Console output capture settings
    console_output_enabled: bool = Field(
        default=False,
        description="Enable captured stdout/stderr in reports (--beacon-console-output)",
    )
    console_output_lines: int = Field(
        default=50,
        description="Number of last stdout/stderr lines to keep per phase per test (--beacon-console-lines)",
    )


def get_settings() -> Settings:
    """
    Get configuration settings.
    """
    return Settings()
