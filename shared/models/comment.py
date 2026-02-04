from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from shared.models.base import Base


class WineCommentBase(SQLModel):
    wine_id: int = Field(foreign_key="wine.id", index=True)
    user_id: str = Field(index=True)
    rating: int = Field(ge=1, le=10)
    text: str = Field(max_length=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WineComment(WineCommentBase, Base, table=True):
    wine: Optional["Wine"] = Relationship(back_populates="comments")
    # user: Optional["User"] = Relationship()