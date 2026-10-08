import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings, warn_if_weak_jwt_secrets
from routers import auth, predictions, stocks, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

warn_if_weak_jwt_secrets()

# Interactive API docs and the OpenAPI schema are only served in local development
app = FastAPI(
    title="InvestIQ API",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(stocks.router)
app.include_router(predictions.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
