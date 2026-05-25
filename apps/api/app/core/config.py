from functools import lru_cache
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./data/metadata/ee_factory_lab.db"
    data_dir: Path = Path("data")
    default_publish_target: str = "quay.io"
    vulnerability_scan_enabled: bool = True
    vulnerability_scan_required: bool = False
    osv_api_base_url: str = "https://api.osv.dev"
    ollama_enabled: bool = False
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def repo_root(self) -> Path:
        if os.getenv("REPO_ROOT"):
            return Path(os.environ["REPO_ROOT"]).resolve()
        return Path(__file__).resolve().parents[4]

    @property
    def config_dir(self) -> Path:
        return self.repo_root / "config"

    @property
    def template_dir(self) -> Path:
        return self.repo_root / "templates"

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir.is_absolute():
            return self.data_dir
        return self.repo_root / self.data_dir

    @property
    def resolved_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if not self.database_url.startswith("sqlite:///"):
            return self.database_url
        sqlite_path = self.database_url.removeprefix("sqlite:///")
        path = Path(sqlite_path)
        if not path.is_absolute():
            path = self.repo_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
