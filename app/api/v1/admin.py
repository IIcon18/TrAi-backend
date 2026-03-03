from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, asc, desc

from app.core.db import get_db
from app.core.rbac import require_admin
from app.models.user import User, RoleEnum
from app.schemas.admin import UserAdminRead, RoleUpdateRequest, RoleUpdateResponse
from typing import List, Optional
import math

router = APIRouter(tags=["admin"])


class UserListResponse:
    def __init__(self, items, total, page, page_size, pages):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
        self.pages = pages


@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None, description="Search by email or nickname"),
    role: Optional[str] = Query(None, description="Filter by role: user|pro|admin"),
    sort_by: str = Query("created_at", pattern="^(created_at|nickname|email)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)

    if search:
        query = query.where(
            User.email.ilike(f"%{search}%") | User.nickname.ilike(f"%{search}%")
        )
    if role:
        try:
            role_enum = RoleEnum(role)
            query = query.where(User.role == role_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    sort_col = getattr(User, sort_by, User.created_at)
    order_fn = asc if sort_order == "asc" else desc
    query = query.order_by(order_fn(sort_col))

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    items = [
        UserAdminRead(
            id=u.id,
            nickname=u.nickname,
            email=u.email,
            role=u.role.value if u.role else "user",
            profile_completed=u.profile_completed,
            created_at=u.created_at,
        )
        for u in users
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total > 0 else 1,
    }


@router.get("/users/{user_id}", response_model=UserAdminRead)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
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
