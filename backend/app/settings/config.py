from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        "office_ai", validation_alias="OFFICE_AI_MYSQL_DATABASE"
    )
    mysql_user: str = Field("office_ai", validation_alias="OFFICE_AI_MYSQL_USER")
    mysql_password: SecretStr = Field(
        SecretStr("local-dev-change-me"),
        validation_alias="OFFICE_AI_MYSQL_PASSWORD",
        repr=False,
    )
    database_host: str = Field("mysql", validation_alias="OFFICE_AI_DATABASE_HOST")
    database_port: int = Field(3306, validation_alias="OFFICE_AI_DATABASE_PORT")
    explicit_database_url: SecretStr | None = Field(
        None, validation_alias="OFFICE_AI_DATABASE_URL", repr=False
    )
    redis_url: SecretStr = Field(
        SecretStr("redis://redis:6379/0"),
        validation_alias="OFFICE_AI_REDIS_URL",
        repr=False,
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

    @field_validator(
        "session_secret",
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
