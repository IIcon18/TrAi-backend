from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import get_db
from app.core.rbac import require_admin
from app.models.user import User, RoleEnum
from app.schemas.admin import UserAdminRead, RoleUpdateRequest, RoleUpdateResponse
from typing import List

router = APIRouter(tags=["admin"])


@router.get("/users", response_model=List[UserAdminRead])
async def list_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех пользователей (только admin)"""
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return [
        UserAdminRead(
            id=u.id,
            nickname=u.nickname,
            email=u.email,
            role=u.role.value if u.role else "user",
            profile_completed=u.profile_completed,
            created_at=u.created_at
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserAdminRead)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Получить детали пользователя (только admin)"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return UserAdminRead(
        id=user.id,
        nickname=user.nickname,
        email=user.email,
        role=user.role.value if user.role else "user",
        profile_completed=user.profile_completed,
        created_at=user.created_at
    )


@router.put("/users/{user_id}/role", response_model=RoleUpdateResponse)
async def update_user_role(
    user_id: int,
    role_data: RoleUpdateRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Изменить роль пользователя (только admin)"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя изменить свою собственную роль"
        )

    # Валидация роли
    try:
        new_role = RoleEnum(role_data.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимая роль: {role_data.role}. Допустимые: user, pro, admin"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.role = new_role
    await db.commit()

    return RoleUpdateResponse(
        message=f"Роль пользователя {user.email} изменена на {new_role.value}",
        user_id=user.id,
        new_role=new_role.value
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Удалить пользователя (только admin)"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить самого себя"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    await db.delete(user)
    await db.commit()

    return {"message": f"Пользователь {user.email} удалён"}
