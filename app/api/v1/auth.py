from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.core.db import get_db
from app.services.auth_service import authenticate_user, register_user, create_access_token
from app.schemas.auth import UserLogin, UserRegister, AuthResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    authenticated_user = await authenticate_user(db, user)
    if not authenticated_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": str(authenticated_user.id)},
        expires_delta=access_token_expires
    )

    return AuthResponse(access_token=access_token)


@router.post("/register", response_model=AuthResponse)
async def register(user: UserRegister, db: AsyncSession = Depends(get_db)):
    try:
        new_user = await register_user(db, user)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": str(new_user.id)},
        expires_delta=access_token_expires
    )

    return AuthResponse(access_token=access_token)