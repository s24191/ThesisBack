from sqlmodel import SQLModel
from typing import Optional

class FollowedWineItem(SQLModel):
    id: int
    name: str
    country: str
    region: Optional[str] = None
    rating: Optional[float] = None
    ratings_count: Optional[int] = None
    best_price: Optional[float] = None
    image_url: Optional[str] = None
