from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.core.db import get_db
from app.services.auth_service import auth_service
from app.schemas.auth import UserLogin, UserRegister, AuthResponse, RefreshTokenRequest

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    """Аутентификация пользователя и выдача JWT токенов"""
    authenticated_user = await auth_service.authenticate_user(db, user)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=auth_service.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": str(authenticated_user.id)},
        expires_delta=access_token_expires
    )

    refresh_token = auth_service.create_refresh_token(
        data={"sub": str(authenticated_user.id)}
    )

    await auth_service.update_refresh_token(db, authenticated_user.id, refresh_token)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/register", response_model=AuthResponse)
async def register(user: UserRegister, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя и выдача JWT токенов"""
    try:
        new_user = await auth_service.register_user(db, user)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    access_token_expires = timedelta(minutes=auth_service.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": str(new_user.id)},
        expires_delta=access_token_expires
    )

    refresh_token = auth_service.create_refresh_token(
        data={"sub": str(new_user.id)}
    )

    await auth_service.update_refresh_token(db, new_user.id, refresh_token)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Обновление access token с помощью refresh token"""
    user = await auth_service.verify_refresh_token(db, request.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    access_token_expires = timedelta(minutes=auth_service.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    return AuthResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,
        token_type="bearer"
    )