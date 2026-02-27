from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_refresh_token(self, refresh_token: str) -> Optional[User]:
        """Получить пользователя по значению refresh-токена (для reuse-detection)."""
        result = await self.db.execute(
            select(User).where(User.refresh_token == refresh_token)
        )
        return result.scalar_one_or_none()

    async def save_refresh_token(
        self,
        user: User,
        refresh_token: str,
        expires: datetime,
    ) -> None:
        user.refresh_token = refresh_token
        user.refresh_token_expires = expires
        await self.db.commit()

    async def revoke_refresh_token(self, user: User) -> None:
        """Аннулировать refresh-токен пользователя (logout / обнаружение повторного использования)."""
        user.refresh_token = None
        user.refresh_token_expires = None
        await self.db.commit()

    async def create_user(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
