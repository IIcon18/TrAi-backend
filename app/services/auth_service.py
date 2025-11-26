from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import UserLogin, UserRegister


class AuthService:
    def __init__(self):
        self.SECRET_KEY = settings.SECRET_KEY
        self.REFRESH_SECRET_KEY = settings.SECRET_KEY + "_refresh"
        self.ALGORITHM = settings.ALGORITHM
        self.ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        # ИСПРАВЛЕНО: убрали .decode('utf-8')
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')  # Декодируем bytes в string для хранения в БД

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        # ИСПРАВЛЕНО: кодируем пароль обратно в bytes для проверки
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.REFRESH_SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    async def update_refresh_token(self, db: AsyncSession, user_id: int, refresh_token: str):
        user = await db.get(User, user_id)
        if user:
            user.refresh_token = refresh_token
            user.refresh_token_expires = datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
            await db.commit()
        return user

    async def verify_refresh_token(self, db: AsyncSession, refresh_token: str):
        try:
            payload = jwt.decode(refresh_token, self.REFRESH_SECRET_KEY, algorithms=[self.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
        except JWTError:
            return None

        user = await db.get(User, int(user_id))
        if user and user.refresh_token == refresh_token and user.refresh_token_expires > datetime.utcnow():
            return user
        return None

    async def authenticate_user(self, db: AsyncSession, login_data: UserLogin) -> Optional[User]:
        user_result = await db.execute(
            select(User).where(User.email == login_data.email)
        )
        user = user_result.scalar_one_or_none()

        if not user or not self.verify_password(login_data.password, user.password):
            return None

        return user

    async def register_user(self, db: AsyncSession, user_data: UserRegister) -> User:
        existing_user = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

        hashed_password = self.hash_password(user_data.password)

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


# Создаем экземпляр сервиса для импорта
auth_service = AuthService()