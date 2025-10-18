from fastapi import APIRouter
from app.schemas.auth import UserLogin, UserRegister, AuthResponse

router = APIRouter()

@router.post("/login", response_model=AuthResponse)
async def login(user: UserLogin):
    # TODO: вызвать сервис авторизации, получить реальный токен
    fake_token = "fake_jwt_token"
    return AuthResponse(
        access_token=fake_token
    )

@router.post("/register", response_model=AuthResponse)
async def register(user: UserRegister):
    # TODO: вызвать сервис регистрации, создать пользователя и токен
    fake_token = "fake_jwt_token"
    return AuthResponse(
        access_token=fake_token
    )