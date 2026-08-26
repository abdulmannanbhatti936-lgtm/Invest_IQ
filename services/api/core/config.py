from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    POSTGRES_USER: str = "investiq"
    POSTGRES_PASSWORD: str = "investiq"
    POSTGRES_DB: str = "investiq"
    DATABASE_URL: str = "postgresql://investiq:investiq@localhost:5432/investiq"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    JWT_SECRET: str
    JWT_REFRESH_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
