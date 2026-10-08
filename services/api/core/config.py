from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    POSTGRES_USER: str = "investiq"
    POSTGRES_PASSWORD: str = "investiq"
    POSTGRES_DB: str = "investiq"
    DATABASE_URL: str = "postgresql://investiq:investiq@127.0.0.1:5435/investiq"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str
    JWT_REFRESH_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Comma-separated list of allowed frontend origins (Architecture.md §11)
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8081,http://127.0.0.1:8081"
    )

    # Auth rate limiting: max attempts per client IP per window (Architecture.md §11)
    AUTH_RATE_LIMIT: int = 10
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60

    # PSX tickers the background jobs ingest, train on and predict for
    TRACKED_TICKERS: str = "SYS,HUBC,OGDC,PPL,MCB,UBL,HBL,MEBL,FFC,EFERT,LUCK,PSO"

    # ML
    MODEL_DIR: str = str(API_ROOT / "ml" / "artifacts")
    DATASET_DIR: str = str(API_ROOT / "ml" / "data" / "raw")
    LOW_CONFIDENCE_THRESHOLD: float = 0.6  # PRD.md FR16
    MIN_HISTORY_DAYS: int = 120  # below this we refuse to predict (PRD.md FR10)

    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("JWT_REFRESH_SECRET")
    @classmethod
    def refresh_secret_differs(cls, v: str, info) -> str:
        if v and v == info.data.get("JWT_SECRET"):
            raise ValueError("JWT_REFRESH_SECRET must differ from JWT_SECRET")
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def tracked_tickers(self) -> list[str]:
        return [t.strip().upper() for t in self.TRACKED_TICKERS.split(",") if t.strip()]


settings = Settings()
