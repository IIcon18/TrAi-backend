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
    return {"message": "Добро пожаловать в TrAi!"}