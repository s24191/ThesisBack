from uuid import UUID

from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

from shared.models.base import Base
from sqlmodel import UniqueConstraint

class WineCommentBase(SQLModel):
    wine_id: int = Field(foreign_key="wine.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    rating: int = Field(ge=1, le=10)
    text: str = Field(max_length=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WineComment(WineCommentBase, Base, table=True):
    __tablename__ = "winecomment"

    __table_args__ = (
        UniqueConstraint("wine_id", "user_id", name="uq_wine_user_review"),
    )

    wine: "Wine" = Relationship(back_populates="comments")
    author: "User" = Relationship(back_populates="wine_comments")
