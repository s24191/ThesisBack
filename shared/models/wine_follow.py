from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint


class WineFollow(SQLModel, table=True):
    __tablename__ = "wine_follows"
    __table_args__ = (
        UniqueConstraint("user_id", "wine_id", name="uq_user_wine_follow"),
    )

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    wine_id: int = Field(foreign_key="wine.id", primary_key=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    notify_price_change: bool = Field(default=True)
    notify_new_store: bool = Field(default=True)
    notify_back_in_stock: bool = Field(default=True)

    wine: "Wine" = Relationship(back_populates="followers")
