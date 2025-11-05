from fastapi import APIRouter
from app.schemas.goal import GoalUpdate

router = APIRouter(prefix="/goals", tags=["goals"])

@router.put("/{goal_id}")
async def update_goal(goal_id: int, goal: GoalUpdate):
    return {"message": "Цель обновлена", "goal_id": goal_id, "data": goal}