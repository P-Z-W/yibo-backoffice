"""Application settings loaded from the local environment file."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the modular FastAPI application."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "毅播云仓管理平台"
    app_version: str = "1.0.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    app_secret_key: str = Field(validation_alias="APP_SECRET_KEY")
    initial_admin_password: str = Field(validation_alias="APP_PASSWORD")
    initial_admin_username: str = "admin"
    session_cookie_name: str = "yibo_session"
    session_max_age: int = 60 * 60 * 12

    db_host: str = Field(default="127.0.0.1", validation_alias="LOCAL_DB_HOST")
    db_port: int = Field(default=3306, validation_alias="LOCAL_DB_PORT")
    db_user: str = Field(default="root", validation_alias="LOCAL_DB_USER")
    db_password: str = Field(default="", validation_alias="LOCAL_DB_PASSWORD")
    db_name: str = Field(default="yibo_backoffice", validation_alias="LOCAL_DB_NAME")
    legacy_db_name: str = "yibo_backoffice_old"

    remote_db_host: str = Field(default="", validation_alias="DB_HOST")
    remote_db_port: int = Field(default=3306, validation_alias="DB_PORT")
    remote_db_user: str = Field(default="", validation_alias="DB_USER")
    remote_db_password: str = Field(default="", validation_alias="DB_PASSWORD")
    remote_db_name: str = Field(default="", validation_alias="DB_NAME")
    remote_db_charset: str = Field(default="utf8mb4", validation_alias="DB_CHARSET")

    legacy_project_path: Path = Path(r"E:\Projects\yibo-backoffice-old")
    storage_path: Path = BACKEND_DIR / "storage"

    invoice_ocr_provider: str = Field(default="baidu", validation_alias="INVOICE_OCR_PROVIDER")
    baidu_ocr_api_key: str = Field(default="", validation_alias="BAIDU_OCR_API_KEY")
    baidu_ocr_secret_key: str = Field(default="", validation_alias="BAIDU_OCR_SECRET_KEY")
    invoice_ocr_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="INVOICE_OCR_TIMEOUT_SECONDS",
    )

    @property
    def invoice_ocr_available(self) -> bool:
        return bool(
            self.invoice_ocr_provider.lower() == "baidu"
            and self.baidu_ocr_api_key
            and self.baidu_ocr_secret_key
        )

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )

    @property
    def secure_cookies(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def local_database_config(self) -> dict[str, object]:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
            "charset": "utf8mb4",
        }

    @property
    def remote_database_config(self) -> dict[str, object]:
        return {
            "host": self.remote_db_host,
            "port": self.remote_db_port,
            "user": self.remote_db_user,
            "password": self.remote_db_password,
            "database": self.remote_db_name,
            "charset": self.remote_db_charset,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
