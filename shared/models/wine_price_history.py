from datetime import datetime
from sqlmodel import SQLModel, Field

class WinePriceHistory(SQLModel, table=True):
    __tablename__ = "wine_price_history"
    id: int | None = Field(default=None, primary_key=True)
    wine_id: int = Field(foreign_key="wines.id", index=True)
    store_id: int | None = Field(default=None, foreign_key="stores.id", index=True)
    price: float
    is_available: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
