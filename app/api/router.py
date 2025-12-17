from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.profile import router as profile_router
from app.api.v1.goals import router as goals_router
from app.api.v1.dishes import router as dishes_router
from app.api.v1.workouts import router as workouts_router
from app.api.v1.progress import router as progress_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(profile_router, prefix="/profile", tags=["profile"])
api_router.include_router(goals_router, prefix="/goals", tags=["goals"])
api_router.include_router(dishes_router, prefix="/dishes", tags=["dishes"])
api_router.include_router(workouts_router, prefix="/workouts", tags=["workouts"])
api_router.include_router(progress_router, prefix="/progress", tags=["progress"])