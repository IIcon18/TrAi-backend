from fastapi import FastAPI
from app.api.router import api_router
from app.core import init_database
from app.core.test_data import create_test_data
from app.core.db import AsyncSessionLocal

app = FastAPI(title="TrAi - your personal training intelligence")

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    await init_database()
    print("Приложение запущено!")

    async with AsyncSessionLocal() as session:
        await create_test_data(session)

@app.get("/")
async def root():
    base_url = "http://localhost:8000"

    return {
        "app": "TrAi",
        "message": "Trai - your personal training intelligence",
        "links": {
            "📊 Dashboard": f"{base_url}/dashboard",
            "💪 Workouts": f"{base_url}/workouts",
            "📈 Progress": f"{base_url}/progress",
            "👤 Profile": f"{base_url}/profile",
            "🎯 Goals": f"{base_url}/goals",
            "🥗 Nutrition": f"{base_url}/nutrition",
            "📚 Docs": f"{base_url}/docs",
            "📖 ReDoc": f"{base_url}/redoc"
        }
    }