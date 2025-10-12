from fastapi import APIRouter

from app.models.workout_test import WorkoutTest

router = APIRouter()

@router.get("/")
async def get_workouts():
    return {"message": "Тренировки"}

@router.post("/test")
async def post_test(test: WorkoutTest):
    return test.dict()
