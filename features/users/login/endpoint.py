from fastapi import APIRouter

router = APIRouter(prefix="/custom/auth/login", tags=["custom-auth"])

@router.post("/")
async def custom_login():
    return {"msg": "Custom login logic here"}
