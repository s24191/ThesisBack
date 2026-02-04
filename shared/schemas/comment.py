from datetime import datetime
from sqlmodel import SQLModel


class WineCommentRead(SQLModel):
    id: int
    user_id: str
    username: str
    rating: int
    text: str
    created_at: datetime


class WineCommentCreate(SQLModel):
    rating: int
    text: str
