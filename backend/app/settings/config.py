from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
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
