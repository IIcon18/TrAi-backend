from fastapi import APIRouter

router = APIRouter()

@router.get("/login")
async def login():
    return {"message": "Авторизация пользователя"}

@router.get("/register")
async def register():
    return {"message": "Регистриция пользователя"}