from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_progress():
    return {"message": "Прогресс пользователя"}