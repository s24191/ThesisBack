from typing import List, Optional
from sqlmodel import SQLModel


class WineOffer(SQLModel):
    shop_name: str
    shop_url: str
    price: float
    image_url: Optional[str] = None


class WineListItem(SQLModel):
    id: int
    name: str

    country: str
    region: Optional[str] = None

    rating: Optional[float] = None
    ratings_count: Optional[int] = None

    best_price: Optional[float] = None
    offers: List[WineOffer] = []
