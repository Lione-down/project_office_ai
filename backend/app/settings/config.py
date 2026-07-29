from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# One file and one UUID field leave a bounded allowance for multipart headers,
# the sanitized filename, boundaries, and framing bytes.
SINGLE_UPLOAD_MULTIPART_OVERHEAD_BYTES = 64 * 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None, extra="ignore", populate_by_name=True
    )

    environment: str = Field("local", validation_alias="OFFICE_AI_ENV")
    log_level: str = Field("INFO", validation_alias="OFFICE_AI_LOG_LEVEL")
    frontend_origin: str = Field(
        "http://localhost:5173", validation_alias="OFFICE_AI_FRONTEND_ORIGIN"
    )
    mysql_database: str = Field(
        "office_ai",
        validation_alias=AliasChoices("OFFICE_AI_MYSQL_DATABASE", "OFFICE_AI_DB_NAME"),
    )
    mysql_user: str = Field(
        "office_ai",
        validation_alias=AliasChoices("OFFICE_AI_MYSQL_USER", "OFFICE_AI_DB_USER"),
    )
    mysql_password: SecretStr = Field(
        SecretStr("local-dev-change-me"),
        validation_alias=AliasChoices(
            "OFFICE_AI_MYSQL_PASSWORD", "OFFICE_AI_DB_PASSWORD"
        ),
        repr=False,
    )
    database_host: str = Field(
        "mysql",
        validation_alias=AliasChoices("OFFICE_AI_DATABASE_HOST", "OFFICE_AI_DB_HOST"),
    )
    database_port: int = Field(
        3306,
        validation_alias=AliasChoices("OFFICE_AI_DATABASE_PORT", "OFFICE_AI_DB_PORT"),
    )
    explicit_database_url: SecretStr | None = Field(
        None, validation_alias="OFFICE_AI_DATABASE_URL", repr=False
    )
    redis_url: SecretStr = Field(
        SecretStr("redis://redis:6379/0"),
        validation_alias="OFFICE_AI_REDIS_URL",
        repr=False,
    )
    master_key: SecretStr | None = Field(
        None, validation_alias="OFFICE_AI_MASTER_KEY", repr=False
    )
    session_secret: SecretStr | None = Field(
        None, validation_alias="OFFICE_AI_SESSION_SECRET", repr=False
    )
    access_token_ttl_seconds: int = Field(
        900, validation_alias="OFFICE_AI_ACCESS_TOKEN_TTL_SECONDS", ge=60
    )
    refresh_token_ttl_seconds: int = Field(
        2_592_000,
        validation_alias="OFFICE_AI_REFRESH_TOKEN_TTL_SECONDS",
        ge=300,
    )
    bootstrap_admin_phone: str | None = Field(
        None, validation_alias="OFFICE_AI_BOOTSTRAP_ADMIN_PHONE"
    )
    bootstrap_admin_password: SecretStr | None = Field(
        None,
        validation_alias="OFFICE_AI_BOOTSTRAP_ADMIN_PASSWORD",
        repr=False,
    )
    files_root: Path = Field(
        Path("/app/files"), validation_alias="OFFICE_AI_FILES_ROOT"
    )
    max_file_bytes: int = Field(
        50 * 1024 * 1024, validation_alias="OFFICE_AI_MAX_FILE_BYTES", ge=1
    )
    max_image_bytes: int = Field(
        20 * 1024 * 1024, validation_alias="OFFICE_AI_MAX_IMAGE_BYTES", ge=1
    )
    max_image_decoded_bytes: int = Field(
        128 * 1024 * 1024,
        validation_alias="OFFICE_AI_MAX_IMAGE_DECODED_BYTES",
        ge=1,
    )
    max_task_bytes: int = Field(
        200 * 1024 * 1024, validation_alias="OFFICE_AI_MAX_TASK_BYTES", ge=1
    )
    max_task_files: int = Field(20, validation_alias="OFFICE_AI_MAX_TASK_FILES", ge=1)
    parsed_root: Path = Field(
        Path("/app/parsed"), validation_alias="OFFICE_AI_PARSED_ROOT"
    )
    max_parsed_output_bytes: int = Field(
        32 * 1024 * 1024,
        validation_alias="OFFICE_AI_MAX_PARSED_OUTPUT_BYTES",
        ge=1,
    )
    max_pdf_pages: int = Field(200, validation_alias="OFFICE_AI_MAX_PDF_PAGES", ge=1)
    max_excel_sheets: int = Field(
        100, validation_alias="OFFICE_AI_MAX_EXCEL_SHEETS", ge=1
    )
    max_excel_non_empty_cells: int = Field(
        300_000,
        validation_alias="OFFICE_AI_MAX_EXCEL_NON_EMPTY_CELLS",
        ge=1,
    )
    max_archive_entries: int = Field(
        10_000, validation_alias="OFFICE_AI_MAX_ARCHIVE_ENTRIES", ge=1
    )
    max_archive_uncompressed_bytes: int = Field(
        250 * 1024 * 1024,
        validation_alias="OFFICE_AI_MAX_ARCHIVE_UNCOMPRESSED_BYTES",
        ge=1,
    )
    max_archive_compression_ratio: int = Field(
        100, validation_alias="OFFICE_AI_MAX_ARCHIVE_COMPRESSION_RATIO", ge=1
    )
    max_office_xml_member_bytes: int = Field(
        16 * 1024 * 1024,
        validation_alias="OFFICE_AI_MAX_OFFICE_XML_MEMBER_BYTES",
        ge=1,
    )
    max_parser_structural_items: int = Field(
        1_500_000,
        validation_alias="OFFICE_AI_MAX_PARSER_STRUCTURAL_ITEMS",
        ge=1,
    )
    parser_timeout_seconds: float = Field(
        30.0, validation_alias="OFFICE_AI_PARSER_TIMEOUT_SECONDS", gt=0
    )
    processing_lease_seconds: int = Field(
        300, validation_alias="OFFICE_AI_PROCESSING_LEASE_SECONDS", ge=1
    )
    clamav_host: str = Field("clamav", validation_alias="OFFICE_AI_CLAMAV_HOST")
    clamav_port: int = Field(
        3310, validation_alias="OFFICE_AI_CLAMAV_PORT", ge=1, le=65535
    )
    clamav_timeout_seconds: float = Field(
        30.0, validation_alias="OFFICE_AI_CLAMAV_TIMEOUT_SECONDS", gt=0
    )
    paddleocr_url: str = Field(
        "http://paddleocr:8080", validation_alias="OFFICE_AI_PADDLEOCR_URL"
    )
    ocr_timeout_seconds: float = Field(
        60.0, validation_alias="OFFICE_AI_OCR_TIMEOUT_SECONDS", gt=0
    )
    max_ocr_response_bytes: int = Field(
        10 * 1024 * 1024,
        validation_alias="OFFICE_AI_MAX_OCR_RESPONSE_BYTES",
        ge=1,
    )
    max_ocr_items: int = Field(
        5000, validation_alias="OFFICE_AI_MAX_OCR_ITEMS", ge=1, le=100_000
    )
    evidence_root: Path = Field(
        Path("/app/evidence"), validation_alias="OFFICE_AI_EVIDENCE_ROOT"
    )
    max_evidence_manifest_bytes: int = Field(
        10 * 1024 * 1024,
        validation_alias="OFFICE_AI_MAX_EVIDENCE_MANIFEST_BYTES",
        ge=1,
    )
    max_evidence_items: int = Field(
        11_563,
        validation_alias="OFFICE_AI_MAX_EVIDENCE_ITEMS",
        ge=1,
        le=100_000,
    )
    ocr_retry_limit: int = Field(
        3, validation_alias="OFFICE_AI_OCR_RETRY_LIMIT", ge=1, le=10
    )
    ocr_retry_backoff_seconds: int = Field(
        30,
        validation_alias="OFFICE_AI_OCR_RETRY_BACKOFF_SECONDS",
        ge=1,
        le=3600,
    )
    ppt_renderer_url: str = Field(
        "http://ppt-renderer:3000",
        validation_alias="OFFICE_AI_PPT_RENDERER_URL",
    )
    libreoffice_url: str = Field(
        "http://libreoffice:8081",
        validation_alias="OFFICE_AI_LIBREOFFICE_URL",
    )
    libreoffice_timeout_seconds: float = Field(
        120,
        validation_alias="OFFICE_AI_LIBREOFFICE_TIMEOUT_SECONDS",
        gt=0,
        le=600,
    )
    rendered_root: Path = Field(
        Path("/app/rendered"),
        validation_alias="OFFICE_AI_RENDERED_ROOT",
    )
    ppt_renderer_timeout_seconds: float = Field(
        120,
        validation_alias="OFFICE_AI_PPT_RENDERER_TIMEOUT_SECONDS",
        gt=0,
        le=600,
    )
    max_presentation_request_bytes: int = Field(
        32 * 1024 * 1024,
        validation_alias="OFFICE_AI_MAX_PRESENTATION_REQUEST_BYTES",
        ge=1024,
        le=50 * 1024 * 1024,
    )
    task_timeout_seconds: int = Field(
        2_700,
        validation_alias="OFFICE_AI_TASK_TIMEOUT_SECONDS",
        ge=60,
        le=86_400,
    )
    chat_max_input_chars: int = Field(
        32_768,
        validation_alias="OFFICE_AI_CHAT_MAX_INPUT_CHARS",
        ge=1,
        le=131_072,
    )
    chat_max_output_tokens: int = Field(
        8_192,
        validation_alias="OFFICE_AI_CHAT_MAX_OUTPUT_TOKENS",
        ge=1,
        le=65_536,
    )
    chat_stream_timeout_seconds: int = Field(
        180,
        validation_alias="OFFICE_AI_CHAT_STREAM_TIMEOUT_SECONDS",
        ge=1,
        le=600,
    )
    chat_heartbeat_seconds: int = Field(
        15,
        validation_alias="OFFICE_AI_CHAT_HEARTBEAT_SECONDS",
        ge=5,
        le=60,
    )
    chat_max_active_runs_per_user: int = Field(
        1,
        validation_alias="OFFICE_AI_CHAT_MAX_ACTIVE_RUNS_PER_USER",
        ge=1,
        le=5,
    )
    chat_runs_per_hour: int = Field(
        20,
        validation_alias="OFFICE_AI_CHAT_RUNS_PER_HOUR",
        ge=1,
        le=1_000,
    )
    chat_runs_per_day: int = Field(
        100,
        validation_alias="OFFICE_AI_CHAT_RUNS_PER_DAY",
        ge=1,
        le=10_000,
    )
    chat_thread_retention_days: int = Field(
        365,
        validation_alias="OFFICE_AI_CHAT_THREAD_RETENTION_DAYS",
        ge=1,
        le=3_650,
    )
    chat_soft_delete_grace_days: int = Field(
        30,
        validation_alias="OFFICE_AI_CHAT_SOFT_DELETE_GRACE_DAYS",
        ge=1,
        le=365,
    )
    chat_backup_retention_days: int = Field(
        30,
        validation_alias="OFFICE_AI_CHAT_BACKUP_RETENTION_DAYS",
        ge=1,
        le=365,
    )
    chat_purge_sla_hours: int = Field(
        24,
        validation_alias="OFFICE_AI_CHAT_PURGE_SLA_HOURS",
        ge=1,
        le=168,
    )
    chat_export_max_bytes: int = Field(
        10_485_760,
        validation_alias="OFFICE_AI_CHAT_EXPORT_MAX_BYTES",
        ge=1_024,
    )
    chat_file_context_mode: str = Field(
        "deck_only",
        validation_alias="OFFICE_AI_CHAT_FILE_CONTEXT_MODE",
        pattern=r"^deck_only$",
    )
    deck_max_slides: int = Field(
        40,
        validation_alias="OFFICE_AI_DECK_MAX_SLIDES",
        ge=3,
        le=40,
    )
    deck_max_context_assets: int = Field(
        20,
        validation_alias="OFFICE_AI_DECK_MAX_CONTEXT_ASSETS",
        ge=1,
        le=20,
    )
    media_max_active_jobs_per_user: int = Field(
        2,
        validation_alias="OFFICE_AI_MEDIA_MAX_ACTIVE_JOBS_PER_USER",
        ge=1,
        le=10,
    )
    image_max_prompt_chars: int = Field(
        4000,
        validation_alias="OFFICE_AI_IMAGE_MAX_PROMPT_CHARS",
        ge=1,
        le=4000,
    )
    image_provider_timeout_seconds: int = Field(
        360,
        validation_alias="OFFICE_AI_IMAGE_PROVIDER_TIMEOUT_SECONDS",
        ge=1,
        le=360,
    )
    media_public_url_input_enabled: bool = Field(
        False,
        validation_alias="OFFICE_AI_MEDIA_PUBLIC_URL_INPUT_ENABLED",
    )
    chat_thinking_default_enabled: bool = Field(
        False,
        validation_alias="OFFICE_AI_CHAT_THINKING_DEFAULT_ENABLED",
    )
    chat_web_search_enabled: bool = Field(
        False,
        validation_alias="OFFICE_AI_CHAT_WEB_SEARCH_ENABLED",
    )

    @property
    def max_upload_body_bytes(self) -> int:
        return self.max_file_bytes + SINGLE_UPLOAD_MULTIPART_OVERHEAD_BYTES

    @field_validator(
        "session_secret",
        "master_key",
        "bootstrap_admin_phone",
        "bootstrap_admin_password",
        mode="before",
    )
    @classmethod
    def empty_auth_value_is_unconfigured(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("session_secret")
    @classmethod
    def validate_session_secret_length(
        cls, value: SecretStr | None
    ) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("session secret must contain at least 32 characters")
        return value

    @field_validator("bootstrap_admin_password")
    @classmethod
    def validate_bootstrap_password_length(
        cls, value: SecretStr | None
    ) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 12:
            raise ValueError("bootstrap password must contain at least 12 characters")
        return value

    @model_validator(mode="after")
    def validate_processing_lease_covers_timeouts(self):
        minimum_lease = max(
            300,
            int(
                self.clamav_timeout_seconds
                + self.parser_timeout_seconds
                + self.ocr_timeout_seconds
            )
            + 60,
        )
        if self.processing_lease_seconds < minimum_lease:
            raise ValueError(
                "processing lease must cover scan/parser timeouts and I/O overhead"
            )
        return self

    @model_validator(mode="after")
    def validate_post_alpha_fail_closed_switches(self):
        if self.chat_web_search_enabled:
            raise ValueError("OFFICE_AI_CHAT_WEB_SEARCH_ENABLED=true is not supported")
        if self.chat_thinking_default_enabled:
            raise ValueError(
                "OFFICE_AI_CHAT_THINKING_DEFAULT_ENABLED must remain false"
            )
        if self.media_public_url_input_enabled:
            raise ValueError(
                "OFFICE_AI_MEDIA_PUBLIC_URL_INPUT_ENABLED=true is not supported"
            )
        return self

    @property
    def database_url(self) -> SecretStr:
        if self.explicit_database_url is not None:
            return self.explicit_database_url
        username = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password.get_secret_value())
        database = quote_plus(self.mysql_database)
        return SecretStr(
            f"mysql+aiomysql://{username}:{password}@{self.database_host}:"
            f"{self.database_port}/{database}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
