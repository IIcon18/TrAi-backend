from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import UserLogin, UserRegister


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


async def authenticate_user(db: AsyncSession, login_data: UserLogin) -> Optional[User]:
    user_result = await db.execute(
        select(User).where(User.email == login_data.email)
    )
    user = user_result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password):
        return None

    return user


async def register_user(db: AsyncSession, user_data: UserRegister) -> User:
    existing_user = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

    hashed_password = hash_password(user_data.password)

    new_user = User(
        email=user_data.email,
        password=hashed_password,
        age=user_data.age,
        lifestyle=user_data.lifestyle,
        height=user_data.height,
        weight=user_data.weight,
        created_at=datetime.utcnow()
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user