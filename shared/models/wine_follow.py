from datetime import datetime
from uuid import UUID
from sqlmodel import SQLModel, Field, Relationship

from shared.models.wine import Wine


class WineFollow(SQLModel, table=True):
    __tablename__ = "wine_follows"
    user_id: UUID = Field(index=True)
    wine_id: int = Field(foreign_key="wine.id", primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    notify_price_change: bool = Field(default=True)
    notify_new_store: bool = Field(default=True)
    notify_back_in_stock: bool = Field(default=True)

    wine: Wine = Relationship(back_populates="followers")