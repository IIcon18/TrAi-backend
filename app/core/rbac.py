from fastapi import Depends, HTTPException, status
from app.core.dependencies import get_current_user
from app.models.user import User, RoleEnum


def require_role(*allowed_roles: RoleEnum):
    """Фабрика зависимостей для проверки роли пользователя."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения этого действия"
            )
        return current_user
    return role_checker


require_admin = require_role(RoleEnum.admin)
require_pro = require_role(RoleEnum.pro, RoleEnum.admin)
