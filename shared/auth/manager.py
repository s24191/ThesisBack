from shared.models.user import User
from shared.auth.user_db import get_user_db
from fastapi import Depends
from fastapi_users import BaseUserManager, UUIDIDMixin
import uuid
import os
SECRET = os.getenv("JWT_SECRET")
if not SECRET:
    raise RuntimeError("manager:JWT_SECRET is not set in .env file.")

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)
