from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, predictions, stocks, users

app = FastAPI(title="InvestIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(stocks.router, prefix="/stocks", tags=["stocks"])

@app.get("/health")
def health_check():
    return {"status": "ok"}