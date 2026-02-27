from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import UserLogin, UserRegister
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self):
        self.SECRET_KEY = settings.SECRET_KEY
        self.REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY
        self.ALGORITHM = settings.ALGORITHM
        self.ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

    # ---------- helpers ----------

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            if not hashed_password or not isinstance(hashed_password, str):
                return False
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception as e:
            print(f"Password verification error: {e}")
            return False

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta if expires_delta
            else timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)

    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.REFRESH_SECRET_KEY, algorithm=self.ALGORITHM)

    def _refresh_expiry(self) -> datetime:
        return datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)

    # ---------- основные операции ----------

    async def authenticate_user(self, repo: UserRepository, login_data: UserLogin) -> Optional[User]:
        try:
            user = await repo.get_by_email(login_data.email)
            if not user:
                print(f"User not found: {login_data.email}")
                return None
            if not self.verify_password(login_data.password, user.password):
                print(f"Password verification failed for: {login_data.email}")
                return None
            print(f"User authenticated successfully: {user.email}")
            return user
        except Exception as e:
            print(f"Authentication error: {e}")
            return None

    async def register_user(self, repo: UserRepository, user_data: UserRegister) -> User:
        existing = await repo.get_by_email(user_data.email)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Пользователь с таким email уже существует",
            )
        new_user = User(
            nickname=user_data.nickname,
            email=user_data.email,
            password=self.hash_password(user_data.password),
            profile_completed=False,
            created_at=datetime.utcnow(),
        )
        return await repo.create_user(new_user)

    async def issue_tokens(self, repo: UserRepository, user: User) -> Tuple[str, str]:
        """Выдать новую пару токенов и сохранить refresh-токен в БД."""
        access_token = self.create_access_token(
            data={"sub": str(user.id), "role": user.role.value},
            expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token = self.create_refresh_token(data={"sub": str(user.id)})
        await repo.save_refresh_token(user, refresh_token, self._refresh_expiry())
        return access_token, refresh_token

    async def rotate_refresh_token(
        self, repo: UserRepository, presented_token: str
    ) -> Optional[Tuple[User, str, str]]:
        """
        Проверить refresh-токен и выполнить ротацию.

        Возвращает (user, access_token, new_refresh_token) при успехе.
        Возвращает None при невалидном/истёкшем/уже использованном токене.

        Обнаружение повторного использования: если JWT-подпись верна, но токена
        нет в БД (уже ротировали) — возможна кража; сбрасываем все токены пользователя.
        """
        # 1. Проверка подписи и срока действия JWT
        try:
            payload = jwt.decode(
                presented_token, self.REFRESH_SECRET_KEY, algorithms=[self.ALGORITHM]
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                return None
        except JWTError:
            return None

        # 2. Поиск по значению токена (не по user_id)
        user = await repo.get_by_refresh_token(presented_token)

        if user is None:
            # Токен валидный JWT, но в БД не найден — повторное использование
            victim = await repo.get_by_id(int(user_id))
            if victim:
                await repo.revoke_refresh_token(victim)
            return None

        # 3. Дополнительная проверка срока из БД (на случай рассинхронизации)
        if not user.refresh_token_expires or user.refresh_token_expires < datetime.utcnow():
            await repo.revoke_refresh_token(user)
            return None

        # 4. Выдать новую пару (старый токен перезаписывается в БД)
        access_token, new_refresh_token = await self.issue_tokens(repo, user)
        return user, access_token, new_refresh_token

    async def logout_user(self, repo: UserRepository, refresh_token: str) -> bool:
        """Отозвать refresh-токен пользователя."""
        try:
            payload = jwt.decode(
                refresh_token, self.REFRESH_SECRET_KEY, algorithms=[self.ALGORITHM]
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                return False
        except JWTError:
            return False

        user = await repo.get_by_id(int(user_id))
        if not user:
            return False

        await repo.revoke_refresh_token(user)
        return True


auth_service = AuthService()
