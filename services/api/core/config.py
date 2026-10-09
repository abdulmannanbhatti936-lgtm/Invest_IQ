import logging
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent

MIN_JWT_SECRET_LENGTH = 32
# Markers of the placeholder values in .env.example and of other obviously unset secrets
_PLACEHOLDER_MARKERS = ("placeholder", "changeme", "change-me", "change_me", "your_", "your-")


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

    # The 18 liquid KSE-100 stocks the model is trained on and forecasts for (approved
    # 2026-10-10, DetailedReport Phase 3). Every other stock shows "no forecast yet".
    TRACKED_TICKERS: str = (
        "OGDC,PPL,MARI,HBL,UBL,MEBL,NBP,PSO,FFC,EFERT,LUCK,MLCF,DGKC,HUBC,ATRL,SYS,PAEL,SAZEW"
    )

    # ML
    # MODEL_DIR holds the promoted models and latest.json, the one the API serves.
    # DATASET_DIR holds the committed datasets. Every training run (CLI or the weekly job)
    # writes only into CANDIDATE_DIR (git-ignored) until a model is promoted (ml/promote.py).
    MODEL_DIR: str = str(API_ROOT / "ml" / "artifacts")
    DATASET_DIR: str = str(API_ROOT / "ml" / "data")
    CANDIDATE_DIR: str = str(API_ROOT / "ml" / "candidates")
    REPORTS_DIR: str = str(API_ROOT / "ml" / "reports")  # committed reports of promoted models
    LOW_CONFIDENCE_THRESHOLD: float = 0.6  # PRD.md FR16
    MIN_HISTORY_DAYS: int = 120  # below this we refuse to predict (PRD.md FR10)

    # Fail-safe: unset means production (strict secret checks, no public /docs). Local .env
    # and CI set ENVIRONMENT=development explicitly.
    ENVIRONMENT: str = "production"

    # hide_input_in_errors: a validation error must never print the settings (they hold secrets)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    @field_validator("JWT_REFRESH_SECRET")
    @classmethod
    def refresh_secret_differs(cls, v: str, info) -> str:
        if v and v == info.data.get("JWT_SECRET"):
            raise ValueError("JWT_REFRESH_SECRET must differ from JWT_SECRET")
        return v

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    def jwt_secret_problems(self) -> list[str]:
        """Names + reasons for JWT secrets that are placeholders or too short (never the values)."""
        problems = []
        for name in ("JWT_SECRET", "JWT_REFRESH_SECRET"):
            value = getattr(self, name)
            if any(marker in value.lower() for marker in _PLACEHOLDER_MARKERS):
                problems.append(f"{name} is a placeholder")
            elif len(value) < MIN_JWT_SECRET_LENGTH:
                problems.append(f"{name} is shorter than {MIN_JWT_SECRET_LENGTH} characters")
        return problems

    @model_validator(mode="after")
    def strong_secrets_outside_development(self) -> "Settings":
        # Refuse to start (API, Celery, Alembic) with forgeable tokens anywhere but local dev
        problems = self.jwt_secret_problems()
        if problems and not self.is_development:
            raise ValueError(
                f"Refusing to start with ENVIRONMENT={self.ENVIRONMENT}: {'; '.join(problems)}. "
                "Set strong random secrets (see README)."
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def candidate_dataset_dir(self) -> Path:
        return Path(self.CANDIDATE_DIR) / "data"

    @property
    def candidate_model_dir(self) -> Path:
        return Path(self.CANDIDATE_DIR) / "models"

    @property
    def tracked_tickers(self) -> list[str]:
        return [t.strip().upper() for t in self.TRACKED_TICKERS.split(",") if t.strip()]


settings = Settings()


def warn_if_weak_jwt_secrets(config: Settings = settings) -> None:
    """Development only (elsewhere startup is refused): make weak secrets impossible to miss."""
    for problem in config.jwt_secret_problems():
        logging.getLogger("core.config").warning(
            "INSECURE JWT SECRET: %s. Anyone can forge login tokens for this instance. "
            "Allowed only because ENVIRONMENT=development.",
            problem,
        )
