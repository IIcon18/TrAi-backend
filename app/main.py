from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.router import api_router
from app.core import init_database
from app.core.test_data import create_test_data, create_admin_user
from app.core.db import AsyncSessionLocal

app = FastAPI(title="TrAi - your personal training intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    await init_database()

    from app.services import s3_service
    await s3_service.ensure_bucket_exists()

    from app.models.user import User

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "test@example.com"))
        if not result.scalar_one_or_none():
            await create_test_data(session)

        result = await session.execute(select(User).where(User.email == "admin@trai.com"))
        if not result.scalar_one_or_none():
            await create_admin_user(session)


@app.get("/")
async def root():
    base_url = "http://localhost:8000"

    return {
        "app": "TrAi",
        "message": "Trai - your personal training intelligence",
        "links": {
            "Dashboard": f"{base_url}/dashboard",
            "Workouts": f"{base_url}/workouts",
            "Progress": f"{base_url}/progress",
            "Profile": f"{base_url}/profile",
            "Goals": f"{base_url}/goals",
            "Nutrition": f"{base_url}/nutrition",
            "Docs": f"{base_url}/docs",
            "ReDoc": f"{base_url}/redoc"
        }
    }