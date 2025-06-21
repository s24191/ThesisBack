from fastapi import APIRouter

router = APIRouter(prefix="/custom/auth/register", tags=["custom-auth"])

@router.post("/")
async def custom_register():
    return {"msg": "Custom registration logic here"}
