from fastapi import APIRouter

from app.schemas.post_workout_test import PostWorkoutTestCreate

router = APIRouter(prefix="/workouts", tags=["workouts"])

@router.get("/")
async def get_workouts():
    return {"message": "Тренировки"}

@router.post("/test")
async def post_test(test: PostWorkoutTestCreate):
    return test.dict()
