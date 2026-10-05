from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import runs, webhooks
from app.config import get_settings
from app.db import engine, init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    engine.dispose()


app = FastAPI(
    title="SafePayout API",
    description="AI-assisted batch payout manager with PayPal integration",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "environment": settings.app_env,
    }


app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(webhooks.router, prefix="", tags=["webhooks"])
