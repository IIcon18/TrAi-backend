from fastapi import FastAPI
from app.api.router import api_router
from app.core import init_database

app = FastAPI(title="TrAi - your personal training intelligence")

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    await init_database()
    print("🚀 Приложение запущено!")

@app.get("/")
async def root():
    return {"message": "Добро пожаловать в TrAi!"}