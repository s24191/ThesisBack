from fastapi import Depends, HTTPException, status
from shared.auth.user_binding import fastapi_users
from shared.models.user import User

current_user = fastapi_users.current_user()

async def current_admin(user: User = Depends(current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user