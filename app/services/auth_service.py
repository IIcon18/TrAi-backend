from datetime import datetime, timedelta
from typing import Optional
import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException
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
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            if not hashed_password or not isinstance(hashed_password, str):
                return False
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            print(f"Password verification error: {e}")
            return False

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
        result = await db.execute(select(User.id).where(User.id == user_id))
        user_data = result.first()

        if user_data:
            user = await db.get(User, user_id)
            if user:
                user.refresh_token = refresh_token
                user.refresh_token_expires = datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
                await db.commit()
                return user
        return None

    async def verify_refresh_token(self, db: AsyncSession, refresh_token: str):
        try:
            payload = jwt.decode(refresh_token, self.REFRESH_SECRET_KEY, algorithms=[self.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
        except JWTError:
            return None

        result = await db.execute(
            select(
                User.id,
                User.email,
                User.refresh_token,
                User.refresh_token_expires
            ).where(User.id == int(user_id))
        )
        user_data = result.first()

        if not user_data:
            return None

        if (user_data[2] == refresh_token and
                user_data[3] and
                user_data[3] > datetime.utcnow()):
            user = User()
            user.id = user_data[0]
            user.email = user_data[1]
            return user

        return None

    async def authenticate_user(self, db: AsyncSession, login_data: UserLogin) -> Optional[User]:
        try:
            result = await db.execute(
                select(
                    User.id,
                    User.email,
                    User.password
                ).where(User.email == login_data.email)
            )
            user_data = result.first()

            if not user_data:
                print(f"User not found: {login_data.email}")
                return None

            if not self.verify_password(login_data.password, user_data[2]):
                print(f"Password verification failed for: {login_data.email}")
                return None

            user = User()
            user.id = user_data[0]
            user.email = user_data[1]

            print(f"User authenticated successfully: {user.email}")
            return user

        except Exception as e:
            print(f"Authentication error: {e}")
            return None

    async def register_user(self, db: AsyncSession, user_data: UserRegister) -> User:
        """Упрощённая регистрация — только nickname, email, password"""
        result = await db.execute(select(User.id).where(User.email == user_data.email))
        if result.first():
            raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

        hashed_password = self.hash_password(user_data.password)

        new_user = User(
            nickname=user_data.nickname,
            email=user_data.email,
            password=hashed_password,
            profile_completed=False,
            created_at=datetime.utcnow()
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        return new_user

auth_service = AuthService()