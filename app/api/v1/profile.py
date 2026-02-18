from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import shutil
import os

from app.core.db import get_db
from app.core.dependencies import get_current_user
from app.core.rbac import require_pro
from app.schemas.profile import (
    ProfileResponse, ProfileUpdate, TelegramConnectRequest,
    TelegramConnectResponse, AIFact, AvatarUploadResponse,
    AITip, AITipsRefreshResponse, ProfileSetupRequest, ProfileSetupResponse
)
from app.models.user import User
from app.models.goal import Goal
from app.models.ai_recommendation import AIRecommendation
from app.models.progress import Progress
from app.services.ai_service import ai_service
from datetime import datetime, timedelta

router = APIRouter(tags=["profile"])


@router.get("/", response_model=ProfileResponse)
async def get_profile(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получить профиль текущего пользователя с AI советами"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        current_goal = None
        if user.current_goal_id:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == user.current_goal_id)
            )
            current_goal = goal_result.scalar_one_or_none()

        ai_tips_models = []

        # Генерируем AI tips только если профиль заполнен
        if user.profile_completed:

            goal_type = "maintenance"
            if current_goal and hasattr(current_goal, 'type'):
                goal_type = current_goal.type.value if hasattr(current_goal.type, 'value') else str(current_goal.type)

            try:
                ai_tips = await ai_service.generate_profile_tips(
                    user_data={
                        "level": user.level.value if user.level else "beginner",
                        "goal": goal_type
                    },
                    progress_data={
                        "workout_frequency": f"{user.weekly_training_goal or 3} раза в неделю",
                        "recovery_trend": "стабильный"
                    }
                )

                ai_tips_models = [AITip(tip=tip) for tip in ai_tips]
            except Exception as ai_err:
                ai_tips_models = [AITip(tip="AI tips temporarily unavailable. Please try again later.")]

        return ProfileResponse(
            id=user.id,
            nickname=user.nickname,
            email=user.email,
            profile_completed=user.profile_completed,
            age=user.age,
            gender=user.gender,
            lifestyle=user.lifestyle.value if user.lifestyle else None,
            height=user.height,
            weight=user.weight,
            initial_weight=user.initial_weight,
            target_weight=user.target_weight,
            daily_calorie_deficit=user.daily_calorie_deficit,
            avatar=user.avatar,
            telegram_connected=user.telegram_connected,
            level=user.level.value if user.level else None,
            weekly_training_goal=user.weekly_training_goal,
            preferred_training_days=user.preferred_training_days,
            current_goal=current_goal,
            ai_calorie_plan=user.ai_calorie_plan,
            created_at=user.created_at,
            ai_tips=ai_tips_models
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке профиля: {str(e)}")


@router.post("/setup", response_model=ProfileSetupResponse)
async def setup_profile(
        profile_data: ProfileSetupRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Дозаполнение профиля после регистрации"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        if user.profile_completed:
            raise HTTPException(status_code=400, detail="Профиль уже заполнен")

        # Обновляем данные профиля
        user.age = profile_data.age
        user.gender = profile_data.gender
        user.lifestyle = profile_data.lifestyle
        user.height = profile_data.height
        user.weight = profile_data.weight
        user.initial_weight = profile_data.weight  # Сохраняем начальный вес
        user.target_weight = profile_data.target_weight
        user.level = profile_data.level
        user.weekly_training_goal = profile_data.weekly_training_goal
        user.profile_completed = True

        await db.commit()
        await db.refresh(user)

        return ProfileSetupResponse(
            success=True,
            message="Профиль успешно заполнен",
            profile_completed=True
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при заполнении профиля: {str(e)}")


@router.put("/", response_model=ProfileResponse)
async def update_profile(
        profile_update: ProfileUpdate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Обновить данные профиля пользователя с AI советами"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        update_data = profile_update.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(user, field, value)

        await db.commit()
        await db.refresh(user)

        current_goal = None
        if user.current_goal_id:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == user.current_goal_id)
            )
            current_goal = goal_result.scalar_one_or_none()

        ai_tips = await ai_service.generate_profile_tips(
            user_data={
                "level": user.level.value if user.level else "beginner",
                "goal": current_goal.type.value if current_goal else "maintenance"
            },
            progress_data={
                "workout_frequency": f"{user.weekly_training_goal or 3} раза в неделю",
                "recovery_trend": "стабильный"
            }
        )

        ai_tips_models = [AITip(tip=tip) for tip in ai_tips]

        return ProfileResponse(
            id=user.id,
            nickname=user.nickname,
            email=user.email,
            profile_completed=user.profile_completed,
            age=user.age,
            gender=user.gender,
            lifestyle=user.lifestyle.value if user.lifestyle else None,
            height=user.height,
            weight=user.weight,
            initial_weight=user.initial_weight,
            target_weight=user.target_weight,
            daily_calorie_deficit=user.daily_calorie_deficit,
            avatar=user.avatar,
            telegram_connected=user.telegram_connected,
            level=user.level.value if user.level else None,
            weekly_training_goal=user.weekly_training_goal,
            preferred_training_days=user.preferred_training_days,
            current_goal=current_goal,
            ai_calorie_plan=user.ai_calorie_plan,
            created_at=user.created_at,
            ai_tips=ai_tips_models
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении профиля: {str(e)}")


@router.post("/refresh-ai-tips", response_model=AITipsRefreshResponse)
async def refresh_ai_tips(
        current_user: User = Depends(require_pro),
        db: AsyncSession = Depends(get_db)
):
    """Обновить AI советы (только pro/admin)"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        current_goal = None
        if user.current_goal_id:
            goal_result = await db.execute(
                select(Goal).where(Goal.id == user.current_goal_id)
            )
            current_goal = goal_result.scalar_one_or_none()

        # Безопасное получение типа цели
        goal_type = "maintenance"
        if current_goal and hasattr(current_goal, 'type'):
            goal_type = current_goal.type.value if hasattr(current_goal.type, 'value') else str(current_goal.type)

        ai_tips = await ai_service.generate_profile_tips(
            user_data={
                "level": user.level.value if user.level else "beginner",
                "goal": goal_type
            },
            progress_data={
                "workout_frequency": f"{user.weekly_training_goal or 3} раза в неделю",
                "recovery_trend": "стабильный"
            }
        )

        ai_tips_models = [AITip(tip=tip) for tip in ai_tips]

        return AITipsRefreshResponse(
            success=True,
            ai_tips=ai_tips_models,
            message="AI советы успешно обновлены"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении AI советов: {str(e)}")


@router.post("/avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Загрузить аватар пользователя"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Можно загружать только изображения")

        os.makedirs("static/avatars", exist_ok=True)

        file_extension = file.filename.split('.')[-1]
        filename = f"user_{user.id}.{file_extension}"
        file_path = f"static/avatars/{filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

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
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Подключить Telegram аккаунт для уведомлений"""
    try:
        user = current_user

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

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
        current_user: User = Depends(require_pro),
        db: AsyncSession = Depends(get_db)
):
    """Получить последние AI рекомендации (только pro/admin)"""
    try:
        facts_result = await db.execute(
            select(AIRecommendation)
            .where(AIRecommendation.user_id == current_user.id)
            .order_by(AIRecommendation.created_at.desc())
            .limit(5)
        )
        facts = facts_result.scalars().all()

        return [AIFact.from_orm(fact) for fact in facts]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке фактов: {str(e)}")


@router.get("/workout-stats")
async def get_workout_stats(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Get workout statistics for the last 7 days for Profile page chart.
    Returns completed workouts count and total weight lifted per day.
    """
    try:
        week_ago = datetime.utcnow() - timedelta(days=6)  # Last 7 days including today
        today = datetime.utcnow()

        # Get all progress records for the last 7 days
        progress_result = await db.execute(
            select(Progress)
            .where(
                Progress.user_id == current_user.id,
                Progress.recorded_at >= week_ago
            )
            .order_by(Progress.recorded_at.asc())
        )
        progress_records = progress_result.scalars().all()

        # Create a dictionary with date as key
        stats_by_date = {}
        for record in progress_records:
            date_key = record.recorded_at.date()
            if date_key not in stats_by_date:
                stats_by_date[date_key] = {
                    'completed_workouts': 0,
                    'total_weight': 0
                }
            stats_by_date[date_key]['completed_workouts'] += record.completed_workouts
            stats_by_date[date_key]['total_weight'] += record.total_lifted_weight

        # Generate data for all 7 days (fill missing days with 0)
        chart_data = []
        for i in range(7):
            date = (week_ago + timedelta(days=i)).date()
            day_name = date.strftime('%a')  # Mon, Tue, Wed, etc.

            stats = stats_by_date.get(date, {'completed_workouts': 0, 'total_weight': 0})

            chart_data.append({
                'date': date.isoformat(),
                'day': day_name,
                'completed_workouts': stats['completed_workouts'],
                'total_weight': round(stats['total_weight'], 1)
            })

        return {
            'chart_data': chart_data,
            'total_workouts_week': sum(day['completed_workouts'] for day in chart_data),
            'total_weight_week': round(sum(day['total_weight'] for day in chart_data), 1)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при загрузке статистики: {str(e)}")