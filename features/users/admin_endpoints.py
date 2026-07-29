from fastapi import APIRouter, Depends
from shared.auth.admin import current_admin
from shared.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("")
async def admin_home(user: User = Depends(current_admin)):
    return {
        "message": "Admin panel access granted",
        "email": user.email,
        "is_superuser": user.is_superuser,
    }