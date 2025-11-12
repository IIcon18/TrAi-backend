from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import shutil
import os

from app.core.db import get_db
from app.core.dependencies import get_current_user  # ← ДОБАВИЛ ЗАЩИТУ
from app.schemas.profile import (
    ProfileResponse, ProfileUpdate, TelegramConnectRequest,
    TelegramConnectResponse, AIFact, AvatarUploadResponse
)
from app.models.user import User
from app.models.goal import Goal
from app.models.ai_recommendation import AIRecommendation

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/", response_model=ProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
    db: AsyncSession = Depends(get_db)
):
    """Получить профиль текущего пользователя"""
    try:
        # ИСПОЛЬЗУЕМ current_user вместо запроса по ID - ДОБАВИЛ ЗАЩИТУ
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем текущую цель пользователя
        current_goal = None
        if user.current_goal_id:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == user.current_goal_id)
            )
            current_goal = goal_result.scalar_one_or_none()

        return ProfileResponse(
            id=user.id,
            email=user.email,
            age=user.age,
            lifestyle=user.lifestyle.value,
            height=user.height,
            weight=user.weight,
            initial_weight=user.initial_weight,
            target_weight=user.target_weight,
            daily_calorie_deficit=user.daily_calorie_deficit,
            avatar=user.avatar,
            telegram_connected=user.telegram_connected,
            telegram_chat_id=user.telegram_chat_id,
            level=user.level.value if user.level else None,
            weekly_training_goal=user.weekly_training_goal,
            preferred_training_days=user.preferred_training_days,
            current_goal=current_goal,
            ai_calorie_plan=user.ai_calorie_plan,
            created_at=user.created_at
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке профиля: {str(e)}")


@router.put("/", response_model=ProfileResponse)
async def update_profile(
        profile_update: ProfileUpdate,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Обновить данные профиля пользователя"""
    try:
        # ИСПОЛЬЗУЕМ current_user вместо запроса - ДОБАВИЛ ЗАЩИТУ
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Обновляем только переданные поля
        update_data = profile_update.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        await db.commit()
        await db.refresh(user)

        # Получаем обновленную цель
        current_goal = None
        if user.current_goal_id:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == user.current_goal_id)
            )
            current_goal = goal_result.scalar_one_or_none()

        return ProfileResponse(
            id=user.id,
            email=user.email,
            age=user.age,
            lifestyle=user.lifestyle.value,
            height=user.height,
            weight=user.weight,
            initial_weight=user.initial_weight,
            target_weight=user.target_weight,
            daily_calorie_deficit=user.daily_calorie_deficit,
            avatar=user.avatar,
            telegram_connected=user.telegram_connected,
            telegram_chat_id=user.telegram_chat_id,
            level=user.level.value if user.level else None,
            weekly_training_goal=user.weekly_training_goal,
            preferred_training_days=user.preferred_training_days,
            current_goal=current_goal,
            ai_calorie_plan=user.ai_calorie_plan,
            created_at=user.created_at
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении профиля: {str(e)}")


@router.post("/avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Загрузить аватар пользователя"""
    try:
        # ИСПОЛЬЗУЕМ current_user - ДОБАВИЛ ЗАЩИТУ
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Проверяем что файл является изображением
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Можно загружать только изображения")

        # Создаем директорию если не существует
        os.makedirs("static/avatars", exist_ok=True)

        # Генерируем имя файла
        file_extension = file.filename.split('.')[-1]
        filename = f"user_{user.id}.{file_extension}"
        file_path = f"static/avatars/{filename}"

        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Обновляем аватар в базе
        user.avatar = f"/{file_path}"
        await db.commit()

        return AvatarUploadResponse(
            success=True,
            avatar_url=user.avatar
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке аватарки: {str(e)}")


@router.post("/connect-telegram", response_model=TelegramConnectResponse)
async def connect_telegram(
        telegram_data: TelegramConnectRequest,
        current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
        db: AsyncSession = Depends(get_db)
):
    """Подключить Telegram аккаунт для уведомлений"""
    try:
        # ИСПОЛЬЗУЕМ current_user - ДОБАВИЛ ЗАЩИТУ
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Обновляем данные Telegram
        user.telegram_connected = True
        user.telegram_chat_id = telegram_data.telegram_chat_id

        await db.commit()

        return TelegramConnectResponse(
            success=True,
            message="Telegram успешно подключен",
            telegram_chat_id=user.telegram_chat_id
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при подключении Telegram: {str(e)}")

@router.get("/ai-facts", response_model=List[AIFact])
async def get_ai_facts(
    current_user: User = Depends(get_current_user),  # ← ДОБАВИЛ ЗАЩИТУ
    db: AsyncSession = Depends(get_db)
):
    """Получить последние AI рекомендации для пользователя"""
    try:
        facts_result = await db.execute(
            select(AIRecommendation)
            .where(AIRecommendation.user_id == current_user.id)  # ← ДОБАВИЛ ЗАЩИТУ - текущий пользователь!
            .order_by(AIRecommendation.created_at.desc())
            .limit(5)
        )
        facts = facts_result.scalars().all()

        return [AIFact.from_orm(fact) for fact in facts]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке фактов: {str(e)}")