from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./policy_causal_lab.db"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_TIMEOUT_SECONDS: float = 90.0
    STORAGE_ROOT: str = "storage/projects"
    STORAGE_BACKEND: str = "local"
    JWT_SECRET_KEY: str = "replace-before-enabling-auth"
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    ENV: str = "development"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def storage_path(self) -> Path:
        return Path(self.STORAGE_ROOT)

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.DATABASE_URL

    @property
    def cors_origins(self) -> list[str]:
        origins = {"http://localhost:3000"}
        for origin in self.FRONTEND_ORIGIN.split(","):
            origin = origin.strip()
            if origin:
                origins.add(origin)
        return sorted(origins)


settings = Settings()
