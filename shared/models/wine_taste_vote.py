from uuid import UUID
from datetime import datetime

from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from shared.models.base import Base


class WineTasteVoteBase(SQLModel):
    wine_id: int = Field(foreign_key="wine.id", index=True)
    user_id: UUID = Field(index=True)

    body: int = Field(ge=0, le=10)
    tannin: int = Field(ge=0, le=10)
    sweetness: int = Field(ge=0, le=10)
    acidity: int = Field(ge=0, le=10)

    created_at: datetime = Field(default_factory=datetime.utcnow)

class WineTasteVote(WineTasteVoteBase, Base, table=True):
    __tablename__ = "winetastevote"
    __table_args__ = (
        UniqueConstraint("wine_id", "user_id", name="uq_wine_user_taste"),
    )

    wine: "Wine" = Relationship(back_populates="taste_votes")
