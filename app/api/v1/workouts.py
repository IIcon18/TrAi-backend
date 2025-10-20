from fastapi import APIRouter

from app.schemas.workout import WorkoutTestCreate

router = APIRouter()

@router.get("/")
async def get_workouts():
    return {"message": "Тренировки"}

@router.post("/test")
async def post_test(test: WorkoutTestCreate):
    return test.dict()
