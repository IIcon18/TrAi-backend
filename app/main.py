from fastapi import FastAPI
from app.api.router import api_router

app = FastAPI(title="TrAi - your personal training intelligence")

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Добро пожаловать в TrAi!"}