from typing import Optional
from uuid import UUID

from fastapi_users import schemas
from pydantic import EmailStr, constr


class UserRead(schemas.BaseUser[UUID]):
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    filter_setting: Optional[str] = None
    filter_active: bool

    class Config:
        orm_mode = True


class UserCreate(schemas.BaseUserCreate):
    username: constr(min_length=3, max_length=30)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    password: str


class UserUpdate(schemas.BaseUserUpdate):
    username: Optional[constr(min_length=3, max_length=30)] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    filter_setting: Optional[str] = None
    filter_active: Optional[bool] = None

    class Config:
        orm_mode = True