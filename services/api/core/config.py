import logging
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent

MIN_JWT_SECRET_LENGTH = 32
LLM_PROVIDERS = ("gemini", "groq", "mistral", "claude")
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

    # Chatbot (Phase 8). The provider and model are configuration only (Architecture.md §6.4
    # deviation, 2026-10-13): groq (default, chosen by the bake-off), gemini (backup), mistral or
    # claude.
    # "mock" is a fixed test provider for the Playwright run, refused outside development.
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = ""
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    CLAUDE_API_KEY: str = ""
    # Optional backup: a 429, 5xx or timeout from the primary retries the same message here once
    LLM_BACKUP_PROVIDER: str = ""
    LLM_BACKUP_MODEL: str = ""
    # Grounding budget (context plus history, in estimated tokens) per provider. Groq's free tier
    # allows 8,000 tokens a minute, so it gets about 4,000: the approved drop order (headline
    # titles, then per-holding charge lines) is applied up front (decided 2026-10-13)
    CHAT_CONTEXT_TOKENS: dict[str, int] = {
        "gemini": 12_000,
        "groq": 4_000,
        "mistral": 12_000,
        "claude": 12_000,
        "mock": 12_000,
    }
    CHAT_LIMIT_PER_WINDOW: int = 10  # messages per user per CHAT_LIMIT_WINDOW_SECONDS
    CHAT_LIMIT_WINDOW_SECONDS: int = 300
    CHAT_LIMIT_PER_DAY: int = 100

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

    @model_validator(mode="after")
    def mock_llm_only_in_development(self) -> "Settings":
        if self.LLM_PROVIDER == "mock" and not self.is_development:
            raise ValueError(
                f"Refusing to start with ENVIRONMENT={self.ENVIRONMENT}: LLM_PROVIDER=mock is a "
                "test provider and only allowed in development."
            )
        return self

    def api_key_for(self, provider: str) -> str:
        return {
            "gemini": self.GEMINI_API_KEY,
            "groq": self.GROQ_API_KEY,
            "mistral": self.MISTRAL_API_KEY,
            "claude": self.CLAUDE_API_KEY,
        }.get(provider, "")

    @property
    def llm_api_key(self) -> str:
        """The key of the configured provider; a placeholder counts as no key."""
        key = self.api_key_for(self.LLM_PROVIDER)
        return "" if any(marker in key.lower() for marker in _PLACEHOLDER_MARKERS) else key

    def _provider_problem(self, provider: str, model: str, setting: str) -> str | None:
        if provider not in LLM_PROVIDERS:
            return f"{setting}={provider!r} is not a supported provider"
        if not model:
            return f"{setting.replace('PROVIDER', 'MODEL')} is not set"
        key = self.api_key_for(provider)
        if not key or any(marker in key.lower() for marker in _PLACEHOLDER_MARKERS):
            return f"{provider.upper()}_API_KEY is not set"
        return None

    def chat_unavailable_reason(self) -> str | None:
        """Why the chat cannot run with this configuration, or None if it can."""
        if self.LLM_PROVIDER == "mock":
            return None
        return self._provider_problem(self.LLM_PROVIDER, self.LLM_MODEL, "LLM_PROVIDER")

    def backup_unavailable_reason(self) -> str | None:
        """Why a configured backup provider cannot be used; None if it can or none is set."""
        if not self.LLM_BACKUP_PROVIDER:
            return None
        return self._provider_problem(
            self.LLM_BACKUP_PROVIDER, self.LLM_BACKUP_MODEL, "LLM_BACKUP_PROVIDER"
        )

    def chat_context_tokens(self, provider: str) -> int:
        return self.CHAT_CONTEXT_TOKENS.get(provider, 12_000)

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


def warn_if_chat_unavailable(config: Settings = settings) -> None:
    """The API starts without an LLM key; the chat then shows its 'unavailable' state."""
    reason = config.chat_unavailable_reason()
    if reason:
        logging.getLogger("core.config").warning("Chat disabled: %s.", reason)
    backup = config.backup_unavailable_reason()
    if backup:
        logging.getLogger("core.config").warning("Chat backup provider disabled: %s.", backup)
