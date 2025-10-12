from fastapi import APIRouter

from app.models.goal import GoalUpdate

router = APIRouter()

@router.get("/update")
async def update_goal(goal: GoalUpdate):
    return {"message": "Цель обновлена", "data": goal}