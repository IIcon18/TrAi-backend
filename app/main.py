from fastapi import FastAPI
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.profile import router as profile_router
from app.routers.goals import router as goals_router
from app.routers.dishes import router as dishes_router
from app.routers.workouts import router as workouts_router
from app.routers.progress import router as progress_router

app = FastAPI(title="TrAi - your personal training intelligence")

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(profile_router, prefix="/profile", tags=["Profile"])
app.include_router(goals_router, prefix="/goals", tags=["Goals"])
app.include_router(dishes_router, prefix="/dishes", tags=["Dishes"])
app.include_router(workouts_router, prefix="/workouts", tags=["Workouts"])
app.include_router(progress_router, prefix="/progress", tags=["Progress"])

@app.get("/")
async def root():
    return {"message": "Добро пожаловать в TrAi!"}