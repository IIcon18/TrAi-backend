from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user, get_user_repository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import auth_service
from app.schemas.auth import (
    UserLogin,
    UserRegister,
    AuthResponse,
    RefreshTokenRequest,
    LogoutRequest,
    UserMeResponse,
)
from app.models.user import User

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(
    user: UserLogin,
    repo: UserRepository = Depends(get_user_repository),
):
    """Аутентификация пользователя и выдача JWT-токенов."""
    authenticated_user = await auth_service.authenticate_user(repo, user)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token = await auth_service.issue_tokens(repo, authenticated_user)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        role=authenticated_user.role.value,
    )


@router.post("/register", response_model=AuthResponse)
async def register(
    user: UserRegister,
    repo: UserRepository = Depends(get_user_repository),
):
    """Регистрация нового пользователя и выдача JWT-токенов."""
    try:
        new_user = await auth_service.register_user(repo, user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    access_token, refresh_token = await auth_service.issue_tokens(repo, new_user)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        role=new_user.role.value,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    repo: UserRepository = Depends(get_user_repository),
):
    """Обновление access-токена с ротацией refresh-токена."""
    result = await auth_service.rotate_refresh_token(repo, request.refresh_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или истёкший refresh-токен",
        )

    user, access_token, new_refresh_token = result

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        role=user.role.value,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    repo: UserRepository = Depends(get_user_repository),
):
    """Завершение сессии: отзыв refresh-токена на сервере."""
    await auth_service.logout_user(repo, request.refresh_token)
    return None


@router.get("/me", response_model=UserMeResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Получить данные текущего авторизованного пользователя."""
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        nickname=current_user.nickname,
        role=current_user.role.value,
        profile_completed=current_user.profile_completed,
    )
