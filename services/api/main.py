from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, users, stocks, predictions

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
app.include_router(predictions.router) # Must be included before stocks.router if paths overlap, but /stocks/{ticker}/prediction vs /stocks/{ticker} should be fine. Actually let's include it.
app.include_router(stocks.router, prefix="/stocks", tags=["stocks"])

@app.get("/health")
def health_check():
    return {"status": "ok"}