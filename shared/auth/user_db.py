from typing import AsyncGenerator

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.user import User
from shared.database import get_session

async def get_user_db(session: AsyncSession = Depends(get_session))-> AsyncGenerator:
    yield SQLAlchemyUserDatabase(session, User)
