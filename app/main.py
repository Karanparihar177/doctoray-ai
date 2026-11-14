
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Independent AI microservice for Doctoray",
)

# Versioned API routes
app.include_router(
    api_router,
    prefix=settings.api_v1_prefix
)


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to Doctoray AI",
        "version": settings.app_version
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "doctoray-ai"
    }
