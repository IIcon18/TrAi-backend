from fastapi import APIRouter

router = APIRouter(prefix="/progress", tags=["progress"])

@router.get("/")
async def get_progress():
    return {"message": "Прогресс пользователя"}